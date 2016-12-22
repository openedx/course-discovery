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

    var org_id = $('#organization-name').data('org_id');
    if (org_id){
        loadAdminUsers(org_id);
    }
});

$(document).on('change', '#id_organization', function (e) {
    var org_id = this.value;

    // it will reset the select input
    $("#id_team_admin").prop("selectedIndex", 0);
    if (org_id) {
        loadAdminUsers(org_id);
    }
});

function loadAdminUsers(org_id) {
    $.getJSON({
        url: '/publisher/api/admins/organizations/'+ org_id +'/users/',
        success: function (data) {
            var teamAdminDropDown = $('#id_team_admin');
            teamAdminDropDown.empty();

            // it will looks same like other django model choice fields
            teamAdminDropDown.append('<option selected="selected">---------</option>');

            $.each(data.results, function (i, user) {
                 teamAdminDropDown.append($('<option> </option>').val(user.id).html(user.full_name));
            });
        }
    });
}
