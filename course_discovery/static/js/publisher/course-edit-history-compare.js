$(document).ready(function () {
});

function decodeEntities(encodedString) {
    var textArea = document.createElement('textarea');
    textArea.innerHTML = encodedString;
    return textArea.value;
}

function hasValidData(){
    for (var i = 0; i < tinyMCE.editors.length; i++) {
        var editor = tinyMCE.editors[i];
        if (editor.dom.select('ins').length > 0) {
            editor.focus();
            return false;
        }

        if (editor.dom.select('del').length > 0) {
            editor.focus();
            return false;
        }
    }
    return true;
}
