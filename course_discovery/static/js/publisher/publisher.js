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
            $tabContent = $("#"+tab_id);
        $(this).parent().find('.course-tabs').removeClass('active');
        $tabContent.parent().find('.content').removeClass('active');

        $(this).addClass('active');
        $tabContent.addClass('active');
    });

    $("#change-admin").click(function (e) {
        e.preventDefault();
        $(".field-admin-name").hide();
        $("#field-team-admin").show();
    });
});
