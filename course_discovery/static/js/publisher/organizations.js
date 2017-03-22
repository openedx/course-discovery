$(document).ready(function(){
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
            var teamAdminDropDown = $('#id_team_admin'),
                selectedTeamAdmin = $('#id_team_admin option:selected').val(),
                organizationInputType = $('#id_organization').attr('type'),
                currentUser = teamAdminDropDown.data('user');
            teamAdminDropDown.empty();

            if (organizationInputType == 'hidden' ) {
                teamAdminDropDown.append('<option>---------</option>');
            } else {
                // it will looks same like other django model choice fields
                teamAdminDropDown.append('<option selected="selected">---------</option>');
            }

            $.each(data.results, function (i, user) {
                if ((selectedTeamAdmin == user.id && organizationInputType === 'hidden') || currentUser == user.id) {
                    teamAdminDropDown.append(
                        $('<option selected="selected"> </option>').val(user.id).html(user.full_name)
                    );
                } else {
                    teamAdminDropDown.append($('<option> </option>').val(user.id).html(user.full_name));
                }
            });
        }
    });
}
