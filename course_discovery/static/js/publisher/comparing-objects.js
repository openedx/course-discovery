    var dmp =new diff_match_patch();
    function launch() {
      var text1 = $("#title").text();
      var text2 = $("#history-title").text();
      var d = dmp.diff_main(text1, text2);
      $("#difference-title").html(dmp.diff_prettyHtml(d));
    }
launch();
