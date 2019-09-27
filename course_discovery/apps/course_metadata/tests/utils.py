def build_salesforce_exception(record_type):
    return 'The Partner of this {} has a Salesforce Configuration, ' \
        'try using {}FactoryNoSignals instead.'.format(record_type, record_type)
