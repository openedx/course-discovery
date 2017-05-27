var dmp = new diff_match_patch();
dmp.Diff_EditCost = 8;

diff_match_patch.prototype.diff_prettyHtml = function (diffs) {
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
                html[x] = '<ins style="background:#e6ffe6;display:inline-block; margin:0 3px">' + text + '</ins>';
                break;
            case DIFF_DELETE:
                html[x] = '<del style="background:#ffe6e6;display:inline-block; margin:0 3px">' + text + '</del>';
                break;
            case DIFF_EQUAL:
                html[x] = '<span>' + text + '</span>';
                break;
        }
    }
    return html.join('');
};

function decodeEntities(encodedString) {
    var textArea = document.createElement('textarea');
    textArea.innerHTML = encodedString;
    return textArea.value;
}
