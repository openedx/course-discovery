$(document).ready(function(){
    var tinymceConfig = {
          plugins: [
            'charactercount','link', 'lists'
          ],
          toolbar: 'undo redo | styleselect | bold italic | bullist numlist outdent indent | link anchor',
          menubar: false,
          statusbar: true,
          skin: false,
          setup: function (editor) {
              keys(editor);
          }
    };

    function keys(editor) {
        editor.on('keydown', function (e) {
            var ContentLength = this.plugins["charactercount"].getCount();
            var maxLength = editor.getElement().maxLength;

            if (maxLength > 0 && ContentLength >= maxLength ) {
                if(e.keyCode != 8 && e.keyCode != 46)
                {
                    tinymce.dom.Event.cancel(e);
                }
            }
        });

        editor.on('paste', function (e) {
            var data = e.clipboardData.getData('Text');
            var ContentLength = this.plugins["charactercount"].getCount();
            var maxLength = editor.getElement().maxLength;

            if (maxLength > 0 && data.length > (maxLength - ContentLength)){
                if(e.keyCode != 8 && e.keyCode != 46)
                {
                    tinymce.dom.Event.cancel(e);
                }
            }
        });
    }

    tinymceConfig["selector"]="textarea";
    tinymce.init(tinymceConfig);
});
