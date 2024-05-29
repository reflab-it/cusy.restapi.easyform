# -*- coding: utf-8 -*-

from plone.restapi.deserializer import json_body
from plone.restapi.services import Service
from plone.restapi.types.utils import get_form_fieldsets
from plone.namedfile.file import NamedBlobFile, NamedBlobImage
from base64 import b64decode


from zExceptions import BadRequest
from zope.component import getMultiAdapter
from zope.interface import alsoProvides

import datetime
import plone.api
import plone.protect
from plone.restapi.serializer.converters import json_compatible

from collective.easyform.fields import FieldExtenderValidator


class EasyFormPost(Service):
    def reply(self):  # noqa: C901
        data = json_body(self.request)
        self.request.form = data


        # Disable CSRF protection
        if "IDisableCSRFProtection" in dir(plone.protect.interfaces):
            alsoProvides(self.request, plone.protect.interfaces.IDisableCSRFProtection)

        easyform_view = getMultiAdapter((self.context, self.request), name="view")
        formview = easyform_view.form(self.context, self.request)
        formview.update()
        fieldsets = get_form_fieldsets(formview)

        # normalize data
        # get grouped (fieldset) data and add to plain dict
        form_data = {}
        if len(fieldsets) > 1:
            for fieldset in fieldsets:
                id_ = fieldset["id"]
                if id_ in data:
                    form_data.update(data[id_])
        else:
            form_data.update(data)

        form = easyform_view.form_instance
        errors = []
        mapping = {}
        for fname in form.schema:
            field = form.schema[fname]
            mapping[fname] = field.title
            field_data = form_data.get(fname, None)

            if field_data and field._type == set:
                try:
                    field_data = form_data[fname] = set(field_data)
                except AttributeError:
                    field_data = form_data[fname] = None
            elif field_data and field._type == datetime.date:
                try:
                    field_data = form_data[fname] = datetime.date.fromisoformat(
                        field_data
                    )
                except AttributeError:
                    field_data = form_data[fname] = None
            elif field_data and field._type == datetime.datetime:
                try:
                    field_data = form_data[fname] = datetime.datetime.fromisoformat(
                        field_data
                    )
                except AttributeError:
                    field_data = form_data[fname] = None
            elif field_data and field._type == NamedBlobFile:
                try:
                    # data is samething like:
                    # 'data:image/png;name=uno.png;base64,blabla...blabla...bla
                    _type, _name, _data = field_data.split(';')
                    _type = _type.replace('data:', '')
                    _name = _name.replace('name=', '')
                    _data = _data.replace('base64,', '')
                    _blob = b64decode(_data)
                    ttt = NamedBlobFile(_blob, _type, _name)
                    field_data = form_data[fname] = ttt
                except AttributeError:
                    field_data = form_data[fname] = None
            elif field_data and field._type == NamedBlobImage:
                try:
                    # data is samething like:
                    # 'data:image/png;name=uno.png;base64,blabla...blabla...bla
                    _type, _name, _data = field_data.split(';')
                    _type = _type.replace('data:', '')
                    _name = _name.replace('name=', '')
                    _data = _data.replace('base64,', '')
                    _blob = b64decode(_data)
                    ttt = NamedBlobImage(_blob, _type, _name)
                    field_data = form_data[fname] = ttt
                except AttributeError:
                    field_data = form_data[fname] = None
            try:
                # validate custom validators
                extra = FieldExtenderValidator(
                    self.context,
                    self.request,
                    easyform_view,
                    field,
                    formview.widgets[field.getName()]
                )
                extra.validate(field_data)
                field.validate(field_data)
            except Exception as error:
                _msg = f'Field: {field.title} has error {str(error)}'
                print(_msg)
                errors.append({"error": error, "message": _msg, "field": field.title})

        if errors:
            # Drop Python specific error classes in order to be able to better handle
            # errors on front-end
            for error in errors:
                error["error"] = "ValidationError"
            #raise BadRequest(errors)
            response = {
                'status': 'error',
                'msg': 'there are errors',
                'success': False,
                'errors': errors
            }

            return response
            
        data = form.updateServerSideData(form_data)
        errors = form.processActions(form_data)
        if errors:
            return BadRequest("Wrong form data.")

        tmp = {}
        for item in data:
            if type(data[item]) is plone.namedfile.file.NamedBlobFile:
                tmp[item] = data[item].filename
            elif type(data[item]) is plone.namedfile.file.NamedBlobImage:
                tmp[item] = data[item].filename
            else:
                tmp[item] = data[item]
        
        have_data_form = True
        try:
            _data = json_compatible(tmp)
        except:
            _data = {}
            have_data_form = False

        response = {
            'status': 'ok',
            'msg': '',
            'success': True,
            'have_data': have_data_form,
            'data': _data,
            'mapping': mapping
        }

        return response
