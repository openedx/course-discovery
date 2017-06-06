$(function () {
    $('#id_image').on('change', function () {
        // max size limit is 1 MB
        var maxFileSize = 1000000,
            $imageError = $('.image-error');

        if (this.files && this.files[0]) {
            if (this.files[0].size > maxFileSize) {
               $imageError.html(gettext('The image file size cannot exceed 1 MB.'));
                $('#id_image').val("");
                $imageError.show();
                $('.course-image-field .errorlist').closest('.has-error').hide();
            } else {
                $imageError.hide();
            }
        }
    });
});
