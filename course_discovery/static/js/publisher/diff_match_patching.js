function diffMatchBugFixHack(decodedString) {

    //This function fixes a critical bug in diffmatch while diffing ul

    var pattern_ul_cleanup = /(<ul>.*?)¶<br>(.*?<\/ul>)/g;
    var pattern_li_ins_fix = /(<ins.*?>)<li>(.*)?<\/li>(<\/ins>)/g;
    var pattern_li_del_fix = /(<del.*?>)<li>(.*)?<\/li>(<\/del>)/g;
    var fixedString = decodedString.replace(pattern_ul_cleanup, "$1$2");

    while (fixedString.length < decodedString.length) {
        decodedString = fixedString;
        fixedString = decodedString.replace(pattern_ul_cleanup, "$1$2");
    }
    fixedString = fixedString.replace(pattern_li_ins_fix, "<li>$1$2$3</li>");
    fixedString = fixedString.replace(pattern_li_del_fix, "<li>$1$2$3</li>");

    fixedString = diffMatchBugFixHack_for_bullets(fixedString)
    return fixedString;
}

function diffMatchBugFixHack_for_bullets(decodedString) {

    //This function fixes a critical bug in diffmatch while diffing ul

    var pattern_ul_cleanup = /(<ol>.*?)¶<br>(.*?<\/ol>)/g;
    var pattern_li_ins_fix = /(<ins.*?>)<ol>(.*)?<\/ol>(<\/ins>)/g;
    var pattern_li_del_fix = /(<del.*?>)<ol>(.*)?<\/ol>(<\/del>)/g;
    var fixedString = decodedString.replace(pattern_ul_cleanup, "$1$2");

    while (fixedString.length < decodedString.length) {
        decodedString = fixedString;
        fixedString = decodedString.replace(pattern_ul_cleanup, "$1$2");
    }
    fixedString = fixedString.replace(pattern_li_ins_fix, "<ol>$1$2$3</ol>");
    fixedString = fixedString.replace(pattern_li_del_fix, "<ol>$1$2$3</ol>");

    return fixedString;
}

function decodeEntities(encodedString) {
    var textArea = document.createElement('textarea');
    textArea.innerHTML = encodedString;
    var renderedValue = textArea.value;
    return diffMatchBugFixHack(renderedValue);
}
