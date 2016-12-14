$(document).ready(function () {
    $("body").click(function() {
        $('.nav-account .wrapper-nav-sub').removeClass('is-shown');
        $('.nav-account .nav-account-user .title').removeClass('is-selected');
    });

    $('.nav-account .nav-item, .wrapper-nav-sub').click(function(e) {
        $subnav = $('.nav-account').find('.wrapper-nav-sub');
        $title = $(this).find('.title');

        if ($subnav.hasClass('is-shown')) {
            $subnav.removeClass('is-shown');
            $title.removeClass('is-selected');
        } else {
            $('.nav-account .nav-item .title').removeClass('is-selected');
            $('.nav-account .wrapper-nav-sub').removeClass('is-shown');
            $title.addClass('is-selected');
            $subnav.addClass('is-shown');
            // if propagation is not stopped, the event will bubble up to the
            // body element, which will close the dropdown.
            e.stopPropagation();
        }
    });

   $(".nav-account-user").click(function (e) {
        e.preventDefault();
        $('.nav-account .wrapper-nav-sub').addClass('is-shown');
        $('.nav-account .nav-account-user .title').addClass('is-selected');
   });

    $("#email-switch").change(function(e) {
        var isEnabled = this.checked ? true : false,
            switchLabel = gettext("OFF");
        e.preventDefault();

        $.ajax({
            url: "/publisher/user/toggle/email_settings/",
            type: "POST",
            data: {is_enabled: isEnabled},
            success: function (response) {
                if (response.is_enabled) {
                    switchLabel = gettext("ON")
                }
                $(".switch-label").html(switchLabel);
            }
        });
    });
});
