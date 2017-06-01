$(document).ready(function () {

    var dmp = new diff_match_patch();
    dmp.Diff_EditCost = 8;

    var tinymceConfig = {
        plugins: [
            'link lists charactercount paste'
        ],
        toolbar: 'showdiff Accept Reject | undo redo | styleselect | bold italic | bullist numlist outdent indent | link anchor',
        menubar: false,
        statusbar: true,
        paste_remove_spans: true,
        paste_remove_styles: true,
        paste_as_text: true,
        paste_auto_cleanup_on_paste: true,
        skin: false,
        forced_root_block: false,
        setup: function (editor) {
            editor.addButton('showdiff', {
                text: 'ShowDiff',
                icon: false,
                onclick: function () {


                    editor.focus();
                    if ($('#id_history_revision').val()){
                        var current_course_object = editor.getContent();
                        var history_object_value = $('#' + editor.id + '_revision').val();
                        var comparision_dev = $('#' + editor.id + '_comparison');
                        var comparison_data = $('#' + editor.id + '_parent');

                        if (history_object_value === 'None')
                            history_object_value = '';

                        var d = dmp.diff_main(history_object_value, current_course_object);
                        dmp.diff_cleanupSemantic(d);
                        $(comparision_dev).html(decodeEntities(dmp.diff_prettyHtml(d)));
                        $(comparison_data).css({"display": "block"});
                        $(comparision_dev).show();
                    }
                }
            });
            editor.addButton('Accept', {
                text: 'Accept All',
                icon: false,
                onclick: function () {
                    editor.focus();
                    if ($('#id_history_revision').val()) {
                        var comparision_dev = $('#' + editor.id + '_comparison');
                        var comparison_data = $('#' + editor.id + '_parent');
                        $(comparison_data).hide();
                        $(comparision_dev).hide();
                    }
                }
            });
            editor.addButton('Reject', {
                text: 'Reject All',
                icon: false,
                onclick: function () {
                    editor.focus();
                    if ($('#id_history_revision').val()) {
                        var comparision_dev = $('#' + editor.id + '_comparison');
                        var value = $('#' + editor.id + '_revision').val();
                        var comparison_data = $('#' + editor.id + '_parent');
                        if (value == 'None')
                            value = '';
                        editor.setContent(value);
                        editor.execCommand('undo');
                        $(comparision_dev).hide();
                        $(comparison_data).hide();
                    }
                }
            });
        }
    };

    tinymceConfig["selector"] = "textarea";
    tinymce.init(tinymceConfig);

    tinymceConfig["selector"] = "#id_title";
    tinymceConfig["toolbar"] = "showdiff Accept Reject";
    tinymce.init(tinymceConfig);
});

$(document).on('click', 'a#close-comparison', function(e){
    e.preventDefault();
    $(this).parent().hide();
});
