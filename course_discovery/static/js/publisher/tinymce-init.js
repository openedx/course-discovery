$(document).ready(function(){
    var tinymceConfig = {
          plugins: [
            'link lists charactercount paste'
          ],
          toolbar: 'undo redo | styleselect | bold italic | bullist numlist outdent indent | link anchor',
          menubar: false,
          statusbar: true,
          paste_remove_spans: true,
          paste_remove_styles: true,
          paste_as_text: true,
          paste_auto_cleanup_on_paste: true,
          skin: false
    };

    tinymceConfig["selector"]="textarea";
    tinymce.init(tinymceConfig);
});
