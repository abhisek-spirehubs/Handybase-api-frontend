from django.contrib import messages

class APIViewMixin:
    """
    Mixin to handle API errors consistently across all auth and dashboard views.
    """
    def handle_api_error(self, request, form, e):
        # e.detail is the dictionary from _extract_detail()
        error_data = e.detail 
        field_errors = error_data.get("field_errors", [])
        global_msg = error_data.get("message")
        
        # SCENARIO 1: A Django Form was provided (e.g., Login, Register)
        if form:
            if field_errors:
                for err in field_errors:
                    field = err.get("field")
                    msg = err.get("message")
                    # Attach to specific form field if it exists
                    if field and field in form.fields:
                        form.add_error(field, msg)
                    else:
                        # Fallback to non-field error
                        form.add_error(None, f"{field}: {msg}" if field else msg)
            
            if global_msg:
                messages.error(request, global_msg)
                # Only add to form if it wasn't already covered by field errors
                if not field_errors:
                    form.add_error(None, global_msg)

        # SCENARIO 2: No Django Form was provided (e.g., Admin manual forms)
        else:
            if global_msg:
                messages.error(request, global_msg)
            
            # Since there is no form to attach field errors to, put them in Django messages
            for err in field_errors:
                field = err.get("field")
                msg = err.get("message")
                
                # Avoid duplicating the global message
                if msg and msg != global_msg:
                    formatted_msg = f"{field}: {msg}" if field else msg
                    messages.error(request, formatted_msg)