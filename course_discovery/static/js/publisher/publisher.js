$(".container a").click(function(event) {
    event.preventDefault();
    $(this).addClass("selected");
    $(this).siblings().removeClass("selected");
    var tab = $(this).attr("href");
    $(".tab-content").not(tab).css("display", "none");
    $(tab).fadeIn();
});
