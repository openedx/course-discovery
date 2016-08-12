$(".administration-navbar .container > button").click(function(event) {
    event.preventDefault();
    $(this).addClass("selected");
    $(this).siblings().removeClass("selected");
    var tab = $(this).data("tab");
    $(".tab-content").not(tab).css("display", "none");
    $(tab).fadeIn();
});

function alertTimeout(wait) {
    setTimeout(function(){
        $('.alert-messages').html('');
    }, wait);
}