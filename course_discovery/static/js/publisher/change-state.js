$(document).ready(function(){
    $('.btn-change-state, .btn-publish').click(function (e) {
        $.ajax({
            type: "PATCH",
            url: $(this).data('change-state-url'),
            data: JSON.stringify({name: $(this).data('state-name')}),
            contentType: "application/json",
            success: function (response) {
                location.reload();
            },
            error: function (response) {
                if (response.responseJSON) {
                    $('#stateChangeError').html(response.responseJSON.name);
                } else {
                    $('#stateChangeError').html(gettext('Something went wrong! please try again later.'));
                }
                $('#stateChangeAlert').show();
                console.log(response);
            }
        });
    });
});
