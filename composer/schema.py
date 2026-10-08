"""Validate public capability schemas, with legacy contract compatibility."""
from jsonschema import Draft7Validator

def object_schema(schema):
    if schema.get('type') == 'object':
        return schema
    return {'type':'object','properties':schema,'required':list(schema),'additionalProperties':False}

def validate_arguments_schema(arguments, schema):
    schema=object_schema(schema)
    Draft7Validator.check_schema(schema)
    errors=sorted(Draft7Validator(schema).iter_errors(arguments),key=lambda e:str(list(e.path)))
    if errors:
        # Do not echo candidate values (which could include sensitive data).
        raise ValueError('Required arguments or argument schema invalid at '+str(list(errors[0].path))+': '+errors[0].validator)
