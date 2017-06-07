$(document).ready(function () {
    // if current object and history object are same don't show the history changes buttons.
    if ($('#id_history_revision').val()) {
        $('.history').each(function () {
            var element_id = this.id.split('_revision')[0];
            var current_course_object = $('#' + element_id).val().trim();
            var history_object_value = $(this).val().trim();

            if (history_object_value === current_course_object) {
                $(this).closest('div').find(".mce-history-changes").hide();
            }
        });
    }
});
