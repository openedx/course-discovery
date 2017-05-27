$(document).ready(function(){
    var dmp = new diff_match_patch();
    dmp.Diff_EditCost = 8;

    diff_match_patch.prototype.diff_prettyHtml = function(diffs) {
        var html = [];
        var pattern_amp = /&/g;
        var pattern_lt = /</g;
        var pattern_gt = />/g;
        var pattern_para = /\n/g;
        for (var x = 0; x < diffs.length; x++) {
          var op = diffs[x][0];    // Operation (insert, delete, equal)
          var data = diffs[x][1];  // Text of change.
          //var text = data.replace(pattern_amp, '&amp;').replace(pattern_lt, '&lt;')
          //    .replace(pattern_gt, '&gt;').replace(pattern_para, '&para;<br>');
          var text = data.replace(pattern_amp, '&amp;').replace(pattern_lt, '&lt;')
              .replace(pattern_gt, '&gt;').replace(pattern_para, '<br>');
          switch (op) {
            case DIFF_INSERT:
              html[x] = '<ins style="background:#e6ffe6;">' + text + '</ins>';
              break;
            case DIFF_DELETE:
              html[x] = '<del style="background:#ffe6e6;">' + text + '</del>';
              break;
            case DIFF_EQUAL:
              html[x] = '<span>' + text + '</span>';
              break;
          }
        }
    return html.join('');
  };



    var tinymceConfig = {
          plugins: [
            'link lists charactercount paste'
          ],
          toolbar: 'showdiff Accept Reject |undo redo | styleselect | bold italic | bullist numlist outdent indent | link anchor',
          menubar: false,
          statusbar: true,
          paste_remove_spans: true,
          paste_remove_styles: true,
          paste_as_text: true,
          paste_auto_cleanup_on_paste: true,
          skin: false,
          forced_root_block : false,
          setup: function(editor) {
                editor.addButton('showdiff', {
                    text: 'ShowDiff',
                    icon: false,
                    onclick: function() {

                        editor.focus();
                        var current_course_object = editor.getContent();
                        var history_object_value = $('#' + editor.id + '_revision').val();
                        if (history_object_value == 'None')
                            history_object_value = '';

                        var d = dmp.diff_main(history_object_value, current_course_object);
                        dmp.diff_cleanupSemantic(d)
                        document.getElementById('loadDiff').innerHTML = decodeEntities(dmp.diff_prettyHtml(d));
                        $('#showDiffModal').show();
                    }
                });
              editor.addButton('Accept', {
                    text: 'Accept All',
                    icon: false,
                    onclick: function() {
                        editor.focus();

                    }
                });
              editor.addButton('Reject', {
                    text: 'Reject All',
                    icon: false,
                    onclick: function() {
                        editor.focus();
                        var value = $('#' + editor.id + '_revision').val();
                        if (value == 'None')
                            value = '';
                        editor.setContent(value);

                    }
                });
            }
    };

    tinymceConfig["selector"]="textarea";
    tinymce.init(tinymceConfig);

    tinymceConfig["selector"]= "#id_title";
    tinymceConfig["toolbar"] = "showdiff Accept Reject";
    tinymce.init(tinymceConfig);
});
