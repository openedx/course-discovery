def build_salesforce_exception(record_type):
    return 'The Partner of this {record_type} has a Salesforce Configuration, ' \
        'try using {record_type}FactoryNoSignals instead.'.format(record_type=record_type)
