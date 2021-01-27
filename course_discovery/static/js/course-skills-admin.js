require('jquery');


function excludeCourseSkill(event) {
    $('.excluded-skills .item').append(
      $(event.target.parentElement.outerHTML)
    );

    let skillId = event.target.parentElement.dataset.skillId;
    $('#id_exclude_skills option[value="' + skillId  + '"]').attr('selected', true)
    $('#id_include_skills option[value="' + skillId  + '"]').attr('selected', false)

    event.target.parentElement.remove();

}

function includeCourseSkill(event) {
    $('.course-skill .item').append(
      $(event.target.parentElement.outerHTML)
    );

    let skillId = event.target.parentElement.dataset.skillId;
    $('#id_include_skills option[value="' + skillId  + '"]').attr('selected', true)
    $('#id_exclude_skills option[value="' + skillId  + '"]').attr('selected', false)

    event.target.parentElement.remove();
}


$(function(){
  // Exclude course skill.
  $('.course-skill').on('click', '.remove', excludeCourseSkill);

  // Include course skills.
  $('.excluded-skills').on('click', '.remove', includeCourseSkill);

});
