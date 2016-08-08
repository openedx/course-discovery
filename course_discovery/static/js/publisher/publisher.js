$(".container > button").click(function(event) {
    $(this).addClass("selected");
    $(this).siblings().removeClass("selected");
    var tab = $(this).data("tab");
    $(".tab-content").not(tab).css("display", "none");
    $(tab).fadeIn();
});
