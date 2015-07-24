import sys, time
import serial
import numpy as np
import cv2, cv2.cv as cv
from Tkinter import *

# =================== Program constants ===================

_face_cascade_config_path = 'haarcascade_frontalface_default.xml'
# _serial_port_name = '/dev/tty.usbserial-A603UZHR'
_serial_port_name = '/dev/tty.Bluetooth-Incoming-Port'

_frame_rate = 30

# Delay between image processing iterations, increase to speed up performance
_capture_delay = 0.2

# Delay between camera captures in seconds
_capture_hold_time = 2

# Precision slack for face positioning
_precision = 0.05

# Image property bounds
_max_contrast = 3
_min_contrast = 0.2
_max_brightness = 100
_min_brightness = -100

# Default values
_default_contrast = 0.5
_default_brightness = 0.5
_default_saturation = 0.5

_default_min_face_dim = {'x': 0.1, 'y': 0.1}

_default_center_x = 0.5
_default_center_y = 0.4

_default_num_people = 1
_default_num_pictures = 2
_default_search_timeout = 10 # in secs

# scale factor for displayed image on laptop
_scale_factor = 2.0

# pan and tilt speed in servo duty cycle increments
_tilt_speed = 1
_pan_speed = 1
_fast_tilt_speed = 3
_fast_pan_speed = 2

# map from one scale to another
def linear_map(new_min, new_max, old_min, old_max, value):
  m = float(new_min - new_max) / (old_min - old_max)
  b = new_min - old_min
  return m * value + b

# Initialize facial detection cascade classifier
faceCascade = cv2.CascadeClassifier(_face_cascade_config_path)

# Program states
IDLE = 0
SCANNING = 1
CENTERING = 2

# =================== Image Processing ===================
class SelfieBot:
  def __init__(self):
    print 'Initializing selfie bot...'
    print 'Connecting to serial port ' + _serial_port_name
    self.serial = serial.Serial(writeTimeout=0, timeout=0)
    self.serial.baudrate = 9600
    self.serial.port = _serial_port_name
    self.serial.close()
    self.serial.open()
    self.serial.flush()

    # Init video capture
    self.video_capture = cv2.VideoCapture(0)
    self.video_capture.set(cv.CV_CAP_PROP_FRAME_WIDTH, 20);

    self.fwidth = self.video_capture.get(cv.CV_CAP_PROP_FRAME_WIDTH)
    self.fheight = self.video_capture.get(cv.CV_CAP_PROP_FRAME_HEIGHT)
    print 'Camera dimensions: ' + str(self.fwidth) + ' x ' + str(self.fheight)

    self._precision_x_pixels = int(_precision * self.fwidth)
    self._precision_y_pixels = int(_precision * self.fheight)

    # =================== Init bot variables ===================

    # Initial state is inactive
    self.state = IDLE

    self.image_num = 0

    self.start_time = time.time()
    self.hold_time_start = time.time()
    self.scan_start = time.time()

    # =================== Default user parameters ===================
    # Desired facial positioning center as a fraction of the frame size
    self.set_parameter('center_x')
    self.set_parameter('center_y')

    # Minimum required face size as a fraction of the screen size
    self.set_parameter('min_face_dim')

    # set the max number of people in the picture
    self.set_parameter('num_people')

    # set the number of pictures to take
    self.set_parameter('num_pictures')

    # people search timeout
    self.set_parameter('search_timeout')

    # set image properties
    self.set_parameter('contrast')
    self.set_parameter('brightness')
    self.set_parameter('saturation')

  def initialize(self):
    print 'Resetting variables...'
    self.pic_num = 0
    self.frame_num = 0

    self.start_time = time.time()
    self.hold_time_start = time.time()
    self.scan_start = time.time()

    self.set_speeds(_fast_pan_speed, _fast_tilt_speed)

    print 'Activating bot...'
    self.state = SCANNING

  def set_speeds(self, pan, tilt):
    print 'Setting pan and tilt speeds...' + str(pan) + ', ' + str(tilt)
    self.serial.write('p ' + str(pan))
    self.serial.write('t ' + str(tilt))

  def stop(self):
    self.state = IDLE

  def cleanup(self):
    self.stop()

    # Close the serial port
    self.serial.close()
    # Close all active camera windows
    cv2.destroyAllWindows()
    # Release the capture
    self.video_capture.release()

  # set the specified parameter to the given value, or defaults
  def set_parameter(self, parameter, value=None):
    if parameter == 'num_people':
      self._num_people = value if value != None else _default_num_people
      if self.state == CENTERING:
        self.state = SCANNING
        self.scan_start = time.time()

    elif parameter == 'num_pictures':
      self._num_pictures = value if value != None else _default_num_pictures

    elif parameter == 'search_timeout':
      self._scan_timeout = value if value != None else _default_search_timeout

    elif parameter == 'center_x':
      self._center_x = value if value != None else 0.5
      self._center_x_pixels = int(self._center_x * self.fwidth)

    elif parameter == 'center_y':
      self._center_y = value if value != None else 0.4
      self._center_y_pixels = int(self._center_y * self.fheight)

    elif parameter == 'contrast':
      # map from a 0-1 scale
      self._contrast = linear_map(_min_contrast, _max_contrast, 0, 1, value)\
        if value != None else _default_contrast

    elif parameter == 'brightness':
      # map from a 0-1 scale
      self._brightness = linear_map(_min_brightness, _max_brightness, 0, 1, value)\
        if value != None else _default_brightness

    elif parameter == 'saturation':
      self._saturation = value if value != None else _default_saturation

    elif parameter == 'min_face_dim':
      self._min_face_dim = value if value != None else _default_min_face_dim
      self._min_face_x = int(self._min_face_dim['x'] * self.fwidth)
      self._min_face_y = int(self._min_face_dim['y'] * self.fheight)

  # Performs image processing and centering, and takes pictures
  # return True if finished
  def process_image_step(self):
    fstart = time.time()

    if time.time() - self.start_time > _capture_delay:
      # Capture frame-by-frame
      ret, frame = self.video_capture.read()

      # Our operations on the frame come here
      frame = cv2.resize(frame, (int(self.fwidth/_scale_factor), int(self.fheight/_scale_factor)), interpolation=cv2.INTER_AREA)
      gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

      # Adjust image properties
      cv2.convertScaleAbs(frame, frame, self._contrast, self._brightness)
      display_frame = frame

      # init serial communication payload
      payload = ''

      # perform operations if program is active, otherwise idle
      if self.state != IDLE:     
        # reset time
        self.start_time = time.time()

        self.frame_num += 1

        # ------------------------------------------------
        # Perform facial detection

        faces = faceCascade.detectMultiScale(
          gray,
          scaleFactor=1.1,
          minNeighbors=5,
          minSize=(int(self._min_face_x/_scale_factor), int(self._min_face_y/_scale_factor)),
          # flags=cv2.cv.CV_HAAR_SCALE_IMAGE
        )

        # take the top _num_people faces
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[:int(self._num_people)]

        # ------------------------------------------------
        # Find centering parameters

        minx = miny = sys.maxint
        maxx = maxy = 0
        for (x, y, w, h) in faces:
          # Draw a rectangle around the face
          # cv2.rectangle(frame, (int(x/_scale_factor), int(y/_scale_factor)), (int((x+w)/_scale_factor), int((y+h)/_scale_factor)), (0, 255, 0), 2)
          cv2.rectangle(display_frame, (int(x), int(y)), (int((x+w)), int((y+h))), (0, 255, 0), 2)
          minx = min(x, minx)
          maxx = max(x+w, maxx)
          miny = min(y, miny)
          maxy = max(y+h, maxy)

        # ------------------------------------------------

        if self.state == SCANNING:
          if len(faces) < self._num_people and time.time() - self.scan_start < self._scan_timeout\
            or len(faces) == 0 and time.time() - self.scan_start > self._scan_timeout:
            payload = 'sc'  # scan for people until they are all found
          else:
            print 'Centering...'
            self.state = CENTERING
            self.set_speeds(_pan_speed, _tilt_speed)

        elif self.state == CENTERING:
          # being scanning again if we lost everyone
          if len(faces) == 0:
            print 'Scanning...'
            self.set_speeds(_fast_pan_speed, _fast_tilt_speed)
            self.state = SCANNING
            # self.scan_start = time.time()

          # ------------------------------------------------
          # Calculate the difference between the face positioning center and the
          # desired positioning center
          center_x = self._center_x_pixels/_scale_factor
          center_y = self._center_y_pixels/_scale_factor

          offset_x = center_x - (minx + maxx)/2
          offset_y = center_y - (miny + maxy)/2

          if abs(offset_x) < self._precision_x_pixels and abs(offset_y) < self._precision_y_pixels:
            # print 'CENTERED: HOLD IT!!!!!'
            payload = 'cc'

            # Takes a picture after the pose is held for a certain time
            if time.time() - self.hold_time_start > _capture_hold_time:
              # reset hold time
              self.hold_time_start = time.time()
              print "TAKING PICTURE"
              # print minx, maxx, self.fwidth

              # cv2.convertScaleAbs(frame, frame, _contrast, _brightness)
              cv2.imwrite('pics/pic' + str(self.image_num) + '.jpg', frame)

              # Flash the image real quick to make it look like a camera capture!
              cv2.convertScaleAbs(display_frame, display_frame, _max_contrast, _max_brightness)

              self.image_num += 1
              self.pic_num += 1
              if self.pic_num == self._num_pictures:
                self.state = IDLE
          else:
            # ------------------------------------------------
            # construct centering payload

            # reset hold time
            self.hold_time_start = time.time()

            if not abs(offset_x) < self._precision_x_pixels:
              if offset_x < 0:    # turn le ft
                payload += 'r'
              else:               # turn right
                payload += 'l'
            else:
              payload += 'c'
            if not abs(offset_y) < self._precision_y_pixels:
              if offset_y < 0:    # tilt down
                payload += 'd'
              else:               # tilt up
                payload += 'u'
            else:
              payload += 'c'

      # ------------------------------------------------
      # Serial communication
      # sys.stdout.write('\rSending command: ' + payload)
      # sys.stdout.flush()

      # print 'Sending command: ' + payload + '\r'
      if not payload:
        payload = 'nn'
      self.serial.write(payload + '\n')

      response = self.serial.readline()
      # if response:
      #   print "Received " + str(response)
      # ------------------------------------------------

      # Display the resulting frame
      cv2.imshow('cam_capture', display_frame)
      # print time.time() - fstart
# ================================ GUI ================================

class App:
  def __init__(self, bot):
    self.bot = bot

    # Create GUI
    self.root = Tk()

    self.frame = Frame(self.root)
    self.frame.pack()
    
    # Create control buttons
    self.start_button = Button(self.frame, text="Start", command=self.start_camera)
    self.start_button.pack()

    self.stop_button = Button(self.frame, text="Stop", command=self.stop_camera)
    self.stop_button.pack()

    self.quit_button = Button(self.frame, text="Quit", fg="red", command=self.quit_app)
    self.quit_button.pack()

    # Create parameter scales
    self.contrast_scale = Scale(self.frame, label='Contrast', length=200, orient=HORIZONTAL,\
      from_=0, to=1, resolution=0.01, command=lambda val: self.set_parameter('contrast', val))
    self.contrast_scale.set(_default_contrast)
    self.contrast_scale.pack()

    self.brightness_scale = Scale(self.frame, label='Brightness', length=200, orient=HORIZONTAL,\
      from_=0, to=1, resolution=0.01, command=lambda val: self.set_parameter('brightness', val))
    self.brightness_scale.set(_default_brightness)
    self.brightness_scale.pack()

    self.center_x_scale = Scale(self.frame, label='Horizontal Center', length=200, orient=HORIZONTAL,\
      from_=0, to=1, resolution=0.01, command=lambda val: self.set_parameter('center_x', val))
    self.center_x_scale.set(_default_center_x)
    self.center_x_scale.pack()

    self.center_y_scale = Scale(self.frame, label='Vertical Center', length=200, orient=HORIZONTAL,\
      from_=0, to=1, resolution=0.01, command=lambda val: self.set_parameter('center_y', 1-float(val)))
    self.center_y_scale.set(1-_default_center_y)
    self.center_y_scale.pack()

    # Create parameter spin boxes
    nplabel = Label(self.frame, text="Number of People")
    nplabel.pack()
    def_np = StringVar(self.root)
    def_np.set(_default_num_people)
    self.num_people = Spinbox(self.frame, textvariable=def_np,\
      from_=0, to=1000, command=lambda: self.set_parameter('num_people', self.num_people.get()))
    self.num_people.pack()

    npclabel = Label(self.frame, text="Number of Pictures")
    npclabel.pack()
    def_npc = StringVar(self.root)
    def_npc.set(_default_num_pictures)
    self.num_pics = Spinbox(self.frame, textvariable=def_npc,\
      from_=0, to=1000, command=lambda: self.set_parameter('num_pictures', self.num_pics.get()))
    self.num_pics.pack()

    stlabel = Label(self.frame, text="People search timeout")
    stlabel.pack()
    def_st = StringVar(self.root)
    def_st.set(_default_search_timeout)
    self.search_timeout = Spinbox(self.frame, textvariable=def_st,\
      from_=0, to=1000, command=lambda: self.set_parameter('search_timeout', self.num_pics.get()))
    self.search_timeout.pack()

    self.frame.after(50, self.process_image)
    self.running = False
    self.root.mainloop()

  def process_image(self):
    self.bot.process_image_step()
    self.frame.after(50, self.process_image)

  def start_camera(self):
    self.bot.initialize()

  def stop_camera(self):
    self.bot.stop()

  def quit_app(self):
    self.bot.cleanup()
    self.root.destroy()

  def set_parameter(self, parameter, value):
    bot.set_parameter(parameter, float(value))

# ================================ Main ================================

bot = SelfieBot()
app = App(bot)

