$(document).ready(function(){

    $("#change-admin").click(function (e) {
        e.preventDefault();
        $(".field-admin-name").hide();
        $("#field-team-admin").show();
    });

    var org_id = $('#organization-name').data('org_id');
    if (org_id){
        loadAdminUsers(org_id);
    }

    var microMaster = $('#id_is_micromasters'),
        xseries = $('#id_is_xseries');

    if (microMaster.is(':checked')) {
        toggleMicroMaster(true);
    }
    if (xseries.is(':checked')) {
        toggleXseries(true);
    }
    microMaster.click( function(){
        toggleMicroMaster(this.checked);
    });
    xseries.click( function(e){
        toggleXseries(this.checked)
    });

    $('.btn-preview-accept').click(function(e){
        $('#acceptPreviewModal').show();
        $('body').addClass('stopScroll');
    });

    $('.btn-accept').click(function (e) {
        $.ajax({
            type: "PATCH",
            url: $(this).data('url'),
            data: JSON.stringify({preview_accepted: true}),
            contentType: "application/json",
            success: function (response) {
                location.reload();
            },
            error: function (response) {
                addModalError(gettext("Something went wrong!"));
                console.log(response);
            }
        });
    });
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
                organizationInputType = $('#id_organization').attr('type');
            teamAdminDropDown.empty();

            if (organizationInputType == 'hidden' ) {
                teamAdminDropDown.append('<option>---------</option>');
            } else {
                // it will looks same like other django model choice fields
                teamAdminDropDown.append('<option selected="selected">---------</option>');
            }

            $.each(data.results, function (i, user) {
                if (selectedTeamAdmin == user.id && organizationInputType === 'hidden' ) {
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

function toggleMicroMaster (checked) {
    // If is-micromaster checkbox value true from db then show the x-micromaster block.
    $('#micromasters_name_group').toggle(checked);
}

function toggleXseries(checked) {
    // If is-xseries checkbox value true from db then show the x-series block.
    $('#xseries_name_group').toggle(checked);
}
