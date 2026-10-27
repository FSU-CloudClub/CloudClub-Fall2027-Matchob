# Shared Helpers (`matchob_common`)

**Purpose:** Helpers every Lambda can import.
**Tech:** Python package in `src/shared/matchob_common/`, deployed as a Lambda layer.
**Role in the project:** Request parsing, response serialization, validation and auth work the same way in every pipeline. Helpers used by only one pipeline go in that pipeline's folder instead (see its `helpers.md`).

Each stack builds its own copy of the layer from `src/shared`, so a change here reaches every Lambda on the next `sam build`.

## `matchob_common.auth`

| Function | Returns |
|---|---|
| `get_user_id(event)` | The Cognito `sub` from `event["requestContext"]["authorizer"]["claims"]`, or the `X-Local-User` header when running under `sam local`, or `None`. Pass `app.current_event.raw_event`. See [auth.md](auth.md). |

## `matchob_common.http`

| Function | Returns |
|---|---|
| `read_json_body(current_event)` | `(body, None)` or `(None, "Invalid JSON body")`. Pass `app.current_event`. `body` can be any JSON value, or `None` for an empty body, so always validate it next. |
| `to_json(body)` | A JSON string. Pass it to the resolver once: `APIGatewayRestResolver(serializer=to_json)`. DynamoDB returns numbers as `Decimal`, and without this Powertools sends them as strings (`"age": "20"`). |
| `decimal_to_number(value)` | The `json.dumps` hook `to_json` uses. Whole numbers become `int`, others `float`. |

## `matchob_common.validators`

A **validator** takes a raw value from the request body and returns the cleaned value, or raises `ValueError` with a message that finishes the sentence "`<field>` ...". For example, `non_empty_str` raises `ValueError("must be a non-empty string")`, which becomes `"name must be a non-empty string"`.

| Validator | Accepts | Returns |
|---|---|---|
| `non_empty_str` | A string with at least one non-space character | The trimmed string |
| `email` | A string shaped like `a@b.c` | The trimmed string |
| `int_between(low, high)` | A whole number in range. `True`/`False` are rejected even though Python counts them as ints | The number |
| `one_of(*choices)` | One of the given strings, exactly | The string |
| `url_list` | A list of strings starting with `http://` or `https://` | The list, each trimmed |
| `optional_str` | `None` or a non-empty string | `None` or the trimmed string |
| `str_length(low, high)` | A string whose trimmed length is `low` to `high` | The trimmed string |

`int_between`, `one_of` and `str_length` build a validator, so call them in the spec: `int_between(13, 120)`.

### `validate_fields(body, spec, partial)`

Validates a whole request body.

| Parameter | Meaning |
|---|---|
| `body` | The parsed body from `read_json_body` |
| `spec` | `{field: (default, validator)}`. Use `REQUIRED` as the default for fields that must be sent on create. Fields not in `spec` are rejected, which is how backend-only fields are protected |
| `partial` | `False` for create: every `REQUIRED` field must be present and missing optional fields get a copy of their default. `True` for update: any non-empty subset is fine |

Returns `(fields, None)` with cleaned values, or `(None, message)`. The messages, in the order they're checked:

| Message | When |
|---|---|
| `Request body must be a JSON object` | `body` isn't a dict (empty body, list, string, number) |
| `Unknown fields: a, b` | A field isn't in `spec` |
| `<field> is required` | Create only, a `REQUIRED` field is missing |
| `<field> <validator message>` | A validator raised `ValueError` |
| `Provide at least one field to update` | Update only, no fields were sent |

Typical use in a route:

```python
body, error = read_json_body(app.current_event)
if error:
    return {"error": error}, 400
fields, error = validate_fields(body, SPEC, partial=False)
if error:
    return {"error": error}, 400
```

## Adding a helper

- **Generic** (any pipeline could use it): add it here, in the module that fits, and document it in this file.
- **One pipeline only:** add it to `src/<pipeline>/<name>_helpers.py` and document it in `docs/<pipeline>/helpers.md`. Give the file a pipeline-specific name, not `helpers.py`, because `pytest.ini` puts every pipeline folder on the same import path.
- Add a new validator only if none above fits. It must follow the same rule: return the cleaned value or raise `ValueError("must ...")`.

---

New to a term? See the [glossary](glossary.md).
