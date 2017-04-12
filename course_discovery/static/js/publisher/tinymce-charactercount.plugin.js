/**
 * Credit: https://amystechnotes.com/2015/05/06/tinymce-add-character-count/
 * This is a slightly modified version to work with more recent TinyMCE version, fix some code styling and don't trim 
 * trailing and leading whitespaces from count.
 */

tinymce.PluginManager.add('charactercount', function (editor) {
  var _self = this;

  function update() {
    editor.theme.panel.find('#charactercount').text(['Characters: {0}', _self.getCount()]);
  }

  editor.on('init', function () {
    var statusbar = editor.theme.panel && editor.theme.panel.find('#statusbar')[0];

    if (statusbar) {
      window.setTimeout(function () {
        statusbar.insert({
          type: 'label',
          name: 'charactercount',
          text: ['Characters: {0}', _self.getCount()],
          classes: 'charactercount',
          disabled: editor.settings.readonly
        }, 0);

        editor.on('setcontent beforeaddundo keyup', update);
      }, 0);
    }
  });

  _self.getCount = function () {
    var tx = editor.getContent({ format: 'raw' });
    var decoded = decodeHtml(tx);
    var decodedStripped = decoded.replace(/(<([^>]+)>)/ig, "").trim();
    var tc = decodedStripped.length;
    return tc;
  };

  function decodeHtml(html) {
    var txt = document.createElement("textarea");
    txt.innerHTML = html;
    return txt.value;
  }
});
