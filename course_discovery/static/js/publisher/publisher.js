$(".administration-nav .tab-container > button").click(function(event) {
    event.preventDefault();
    $(this).addClass("selected");
    $(this).siblings().removeClass("selected");
    var tab = $(this).data("tab");
    $(".tab-content").not(tab).css("display", "none");
    $(tab).fadeIn();
});

$(document).ready(function(){
    $('ul.tabs .course-tabs').click(function(){
        var tab_id = $(this).attr('data-tab');
        $('ul.tabs .course-tabs').removeClass('active');
        $('.content').removeClass('active');

        $(this).addClass('active');
        $("#"+tab_id).addClass('active');
    })

});

function alertTimeout(wait) {
    setTimeout(function(){
        $('.alert-messages').html('');
    }, wait);
}
