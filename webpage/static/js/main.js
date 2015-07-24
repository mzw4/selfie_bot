
$(function() {
  // -------------- Program vars --------------

  var $body = $('body');
  var $title_content = $('#title_content');
  var $title_panel = $('#title_panel')
  var $menu = $('#menu');
  var $menu_background = $('#menu_background')

  var $main_content_panel = $('#main_content_panel');
  var $sections = $('#sections');
  var $section_panels;
  var $footer = $('.footer');
  var $parallax;

  var content_dir = 'content/'
  var backgrounds_dir = 'backgrounds/'
  var menu_height;
  var view_port_dim = {x: $(window).width(), y: $(window).height()};

  // -------------- Handlebars tempaltes --------------
  var sections_template, introduction_content_template, design_content_template,
    hardware_content_template, software_content_template, results_content_template,
    conclusions_content_template, appendix_content_template;

  // -------------- Initialize page --------------
  $title_panel.height(view_port_dim.y);

  // Affix the menu bar to the top
  $menu.affix({
    offset: {
      top: $menu.offset().top,
    }
  })
  menu_height = $menu.height();
  $('#menu_wrapper').height(menu_height);

  backgrounds = ['statue_selfie.jpg']
  $menu_background.css({'background-image': 'url(' + content_dir + backgrounds_dir + backgrounds[0] + ')'});

  // Fade in the content
  $title_content.delay(500).css({'visibility':'visible'}).hide().fadeIn(500, function() {
    populate_page();
    $main_content_panel.fadeIn(500);
    $footer.fadeIn(500);
  });

  // Animate line
  $('.line').delay(200).animate({
    width: '50%'
  }, 1000);

  // -------------- Event bindings --------------

  // Scroll to the section when the menu is clicked
  $('#menu a').on('click', function(e) {
    e.preventDefault();
    $('body').animate({
        scrollTop: $($(this).attr('href')).offset().top - menu_height
    }, 500, 'swing');
  });

  speed = 0.6;
  window.onscroll = function() {
    var offset_y = $(window).scrollTop() + 130
    $parallax.css({
      'background-position': '0 ' + (offset_y * speed) + 'px',
    })
  };

  // -------------- Functions --------------

  function changeBackground() {

    setTimeout(10000);  // wait 10 seconds
  }

  function populate_page() {
    sections_template = Handlebars.compile($('#sections_template').html());
    introduction_content_template = Handlebars.compile($('#introduction_content_template').html());
    design_content_template = Handlebars.compile($('#design_content_template').html());
    hardware_content_template = Handlebars.compile($('#hardware_content_template').html());
    software_content_template = Handlebars.compile($('#software_content_template').html());
    results_content_template = Handlebars.compile($('#results_content_template').html());
    conclusions_content_template = Handlebars.compile($('#conclusions_content_template').html());
    appendix_content_template = Handlebars.compile($('#appendix_content_template').html());

    // Populate the page content
    var section_info = [
      {
        section_id: 'introduction',
        title: 'Introduction',
        img_src: 'content/photo.jpg',
        content: introduction_content_template({}),
      },
      {
        section_id: 'design',
        title: 'Design',
        img_src: 'content/graph2.jpg',
        content: design_content_template({}),
      },
      {
        section_id: 'hardware',
        title: 'Hardware',
        img_src: 'content/hardware.jpg',
        content: hardware_content_template({}),
      },
      {
        section_id: 'software',
        title: 'Software',
        img_src: 'content/software.jpg',
        content: software_content_template({}),
      },
      {
        section_id: 'results',
        title: 'Results',
        img_src: 'content/graph1.png',
        content: results_content_template({}),
      },
      {
        section_id: 'conclusions',
        title: 'Conclusions',
        img_src: 'content/graph1.png',
        content: conclusions_content_template({}),
      },
      {
        section_id: 'appendix',
        title: 'Appendix',
        img_src: 'content/graph1.png',
        content: appendix_content_template({}),
      },
    ];

    // Build content sections and set parameters
    $sections.html(sections_template({ 'sections': section_info }));
    section_info.forEach(function(section) {
      $('#' + section.section_id + ' .banner').css({'background-image': 'url(' + section.img_src + ')'});
    });

    $section_panels = $('.section_panel')
    $parallax = $('.parallax');

    // Set the height of each section to the height of the view port
    $section_panels.css({'min-height': view_port_dim.y - menu_height});
  }
});