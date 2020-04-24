How To Make An Existing Model Field Translatable
================================================
This document explains how to take an existing field on a model and make it translatable. For the instructions, we will assume we are making MyModel.my_field translatable. my_field is a simple text field. Some migrations can be squashed but keeping them all separate makes rolling back much easier if something goes wrong. 

1. Update MyModel to inherit from parler.models.TranslatableModel
2. Add a 'translations' field to the model: ``translations = TranslatedFields(my_field_t=models.CharField())``
3. In the discovery shell, run ``./manage.py makemigrations && make migrate``. This will create the new MyModelTranslation model with a my_field_t field and a back link to MyModel
  i. If you get an error like ERROR BECCA NEEDS TO LOOK UP, try manually editing the generated migration file and removing the ``bases=(parler.models.TranslatedFieldsModelMixin, models.Model)`` bit and then migrating again
4. If my_field is non-nullable or unique, remove those constraints and run ``./manage.py makemigrations && make migrate`` again. Otherwise you will get errors when trying to unapply the migrations.
5. Generate an empty migration file: ``/manage.py makemigrations --empty course_metadata --name "migrate_mymodel_translatable_fields"`` . This will be used to copy MyModel.my_field to MyModelTranslation.my_field_t so no data is lost
6. Fill out the new migration with the following 
  def forwards_func(apps, schema_editor):
    ProgramType = apps.get_model('course_metadata', 'ProgramType')
    ProgramTypeTranslation = apps.get_model('course_metadata', 'ProgramTypeTranslation')
    for programType in ProgramType.objects.all():
        ProgramTypeTranslation.objects.create(
            master_id=programType.pk,
            language_code=settings.PARLER_DEFAULT_LANGUAGE_CODE,
            name_t=programType.name
        )


def backwards_func(apps, schema_editor):
    ProgramType = apps.get_model('course_metadata', 'ProgramType')
    ProgramTypeTranslation = apps.get_model('course_metadata', 'ProgramTypeTranslation')
    for programType in ProgramType.objects.all():
        try:
            translation = ProgramTypeTranslation.objects.get(master_id=programType.pk, language_code=settings.LANGUAGE_CODE)
            programType.name = translation.name_t
            programType.save()  # Note this only calls Model.save()
        except ObjectDoesNotExist:
            # nothing to migrate
            logger.exception('Migrating data from ProgramTypeTranslation for master_id={} DoesNotExist'.format(programType.pk))

  
