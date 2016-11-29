
$(document).ready(function() {
    $('.btn-change-assignment').click(function(e){
        var headers = {
                'X-CSRFToken': Cookies.get('course_discovery_csrftoken')
            },
            apiEndpoint = $(this).data('apiEndpoint'),
            $selectedOption = $('#select-users-by-role option:selected'),
            userId = $selectedOption.val(),
            roleName = $('#role-name').val();
        e.preventDefault();

        $.ajax({
            url: apiEndpoint,
            type: "POST",
            data: {'user_id': userId, 'role_name': roleName},
            headers: headers,
            success: function (response) {
                if (response.success) {
                    $('.user-full-name').text(response.full_name);
                    $selectedOption.val(userId);
                    $("#user-role-container").show();
                    $("#change-role-container").hide();
                    console.log("Role assignment changed successfully.");
                } else {
                    console.log("There was an error in changing role.");
                }
            }
        });
    });

    $("#change-role-assignment").click(function (e) {
        e.preventDefault();
        $("#user-role-container").hide();
        $("#change-role-container").show();
    });

});
