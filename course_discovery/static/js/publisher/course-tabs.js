$(document).ready(function(){
    $(".administration-nav .tab-container > button").click(function(event) {
        event.preventDefault();
        $(this).addClass("selected");
        $(this).siblings().removeClass("selected");
        var tab = $(this).data("tab");
        $(".tab-content").not(tab).css("display", "none");
        $(tab).fadeIn();
    });

    $('ul.tabs .course-tabs').click(function(){
        var tab_id = $(this).attr('data-tab'),
            $tabContent = $(this).closest('.row').siblings("#"+tab_id);
        $(this).parent().find('.course-tabs').removeClass('active');
        $tabContent.siblings('.content').removeClass('active');

        $(this).addClass('active');
        $tabContent.addClass('active');
    });
});
