$(document).ready(function(){
    $('.history').each(function () {
        var dmp = new diff_match_patch();
        var element_id = this.id.split('_revision')[0];

        var current_course_object = $('#' + element_id).val();
        var history_object_value = $(this).val().trim();

        if (history_object_value !='') {
            var d = dmp.diff_main(current_course_object, history_object_value);
            dmp.diff_cleanupEfficiency(d)
            tinymce.get(element_id).setContent(dmp.diff_prettyHtml(d))
        }
    });
});
