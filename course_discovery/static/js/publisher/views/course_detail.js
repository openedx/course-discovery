
$(document).ready(function() {
    $('.btn-change-assignment').click(function(e){
        var apiEndpoint = $(this).data('api-endpoint'),
            roleName = $(this).data('role'),
            $selectedOption = $('#selectUsers-' + roleName + ' option:selected'),
            userId = $selectedOption.val(),
            userName = $selectedOption.text();
        e.preventDefault();

        $.ajax({
            url: apiEndpoint,
            type: 'PATCH',
            data: JSON.stringify({'user': userId}),
            contentType: 'application/json',
            success: function (response) {
                $('#userFullName-' + roleName).text(userName);
                $selectedOption.val(userId);
                $('#userRoleContainer-' + roleName).show();
                $('#changeRoleContainer-' + roleName).hide();
            }
        });
    });

    $('.change-role-assignment').click(function (e) {
        var roleName = $(this).data('role');
        e.preventDefault();
        $('#changeRoleContainer-' + roleName).show();
        $('#userRoleContainer-' + roleName).hide();
    });

});
