$('.remove-image').click(function (e) {
    e.preventDefault();
    $('.course-image-input').removeClass('hidden');
    $('.course-image-thumbnail').hide();
    $('.course-image-field a').hide();
    $('input#image-clear_id').prop('checked', true);
});

// If file selected mark checkbox unchecked otherwise checked.
$('input#id_image').change(function (e) {
    var clearImageInput = $('input#image-clear_id');
    e.preventDefault();
    if (this.files && this.files[0]) {
        clearImageInput.prop('checked', false);
    } else {
        clearImageInput.prop('checked', true);
    }
});
