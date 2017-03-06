
var dmp = new diff_match_patch();
dmp.Diff_EditCost = 8;
function showDiff($object, $historyObject, $outputDiv) {
    var d = dmp.diff_main($historyObject.text(), $object.text());
    dmp.diff_cleanupEfficiency(d);
    $outputDiv.html(dmp.diff_prettyHtml(d));
    $historyObject.hide();
    $outputDiv.show();
}

function showDiffCourseDetails(currentObject, historyObject, $outputDiv) {
    var d = dmp.diff_main(currentObject, historyObject);
    dmp.diff_cleanupEfficiency(d);
    $outputDiv.html(dmp.diff_prettyHtml(d));
    $outputDiv.show();
}
