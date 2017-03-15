$(function () {
    $('#id_image').on('change', function () {
        // max size limit is 1 MB
        var maxFileSize = 1000000;

        if (this.files && this.files[0]) {
            if (this.files[0].size > maxFileSize) {
               $('.image-error').append(gettext('The image file size cannot exceed 1 MB.'));
                $('#id_image').val("");
            } else {
                $('.image-error').empty();
            }
        }
    });
});
