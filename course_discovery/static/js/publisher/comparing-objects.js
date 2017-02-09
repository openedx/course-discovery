$(document).on('click', '.btn-show-changes', function (e) {

    if ($(this).hasClass('show')){
        $('.field-container').each(function () {
            showDiff($(this).find('span.object'), $(this).find('span.history-object'), $(this).find('span.show-diff'));
        });
        $(this).text(gettext('Hide changes'));
        $(this).removeClass('show');
    } else {
        $('.history-object').show();
        $('.show-diff').hide();
        $(this).text(gettext('Show changes'));
        $(this).addClass('show');

    }
});

var dmp = new diff_match_patch();
function showDiff($object, $historyObject, $outputDiv) {
    var d = dmp.diff_main($historyObject.text(), $object.text());
    $outputDiv.html(dmp.diff_prettyHtml(d));
    $historyObject.hide();
    $outputDiv.show();
}

function showDiffCourseDetails(currentObject, historyObject, $outputDiv) {
    var d = dmp.diff_main(currentObject, historyObject);
    $outputDiv.html(dmp.diff_prettyHtml(d));
    $outputDiv.show();
}

