$(document).ready(function(){
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

$(document).on('click', '.btn-edit-preview-url', function (e) {
    var $previewUrl = $('.preview-url'),
        currentUrl = $previewUrl.find('a').attr('href'),
        html = '<input id="id-review-url" type="text" value=' + currentUrl + '>';

    $(this).addClass('btn-save-preview-url').removeClass('btn-edit-preview-url');
    $(this).text(gettext("Save"));
    $('.preview-status').remove();
    $previewUrl.html(html);
    $('#id-review-url').focus();
});

$('.btn-preview-decline').click(function (e) {
    $('#decline-comment').toggle();
});

$(document).on('click', '.btn-save-preview-url', function (e) {
    preview_url = $('#id-review-url').val();
    if (!preview_url) {
        showInvalidPreviewUrlError();
        return
    }
    $.ajax({
        type: "PATCH",
        url: $(this).data('url'),
        data: JSON.stringify({'preview_url': preview_url}),
        contentType: "application/json",
        success: function (response) {
            location.reload();
        },
        error: function (response) {
            showInvalidPreviewUrlError();
        }
    });
});

function showInvalidPreviewUrlError() {
    $('#id-review-url').addClass('has-error');
    $('.error-message').html(gettext("Please enter a valid URL."));
}
