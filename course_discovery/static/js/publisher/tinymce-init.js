$(document).ready(function(){
    var tinymceConfig = {
          plugins: [
            'link lists charactercount paste'
          ],
          toolbar: 'addbutton removebutton |undo redo | styleselect | bold italic | bullist numlist outdent indent | link anchor',
          menubar: false,
          statusbar: true,
          paste_remove_spans: true,
          paste_remove_styles: true,
          paste_as_text: true,
          paste_auto_cleanup_on_paste: true,
          skin: false,
          forced_root_block : false,
          setup: function(editor) {
                function monitorNodeChange() {
                    var btn = this;
                    editor.on('NodeChange', function(e) {

                        var trackElem = getInsDelElement(e.element);
                        btn.disabled((trackElem == null) || (trackElem.nodeName != 'DEL' && trackElem.nodeName != 'INS'));
                    });
                }
                editor.addButton('addbutton', {
                    text: 'Accept',
                    icon: false,
                    onclick: function() {
//
                        var trackElem = getInsDelElement(editor.selection.getNode());
                        if (trackElem != null && trackElem.nodeName === 'INS') {

                            removeTrackingElement(trackElem);
                        }
                        if (trackElem.nodeName === 'DEL') {
                            trackElem.remove();
                        }
                    },
                    onpostrender: monitorNodeChange
                });

                editor.addButton('removebutton', {
                    text: 'Reject',
                    icon: false,
                    onclick: function() {
                        var trackElem = getInsDelElement(editor.selection.getNode());
                        if (trackElem != null && trackElem.nodeName === 'DEL') {
                            removeTrackingElement(trackElem);
                        }
                        if (trackElem.nodeName === 'INS') {
                            trackElem.remove();
                        }
                    },
                    onpostrender: monitorNodeChange
                });
            }
    };

    function getInsDelElement(elem)
    {
        if (elem == null)
        {
            return null;
        }
        else if (elem.nodeName === 'INS' || elem.nodeName === 'DEL')
        {
            return elem;
        }
        return getInsDelElement(elem.parentElement);
    }

    function removeTrackingElement(elem)
    {
        $(elem).replaceWith($(elem).contents());
    }

    tinymceConfig["selector"]="textarea";
    tinymce.init(tinymceConfig);

    tinymceConfig["selector"]= "#id_title";
    tinymceConfig["toolbar"] = "addbutton removebutton";
    tinymce.init(tinymceConfig);

});
