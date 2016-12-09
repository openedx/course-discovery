$(document).ready(function() {
    var box = $('#id_comment');
   $("#id_submit").click(function(event){
       if( !box.val() ) {
            box.addClass('has-error');
            box.focus();
        }
       else{
           $("#frm_comment").submit();
       }

   });
});
