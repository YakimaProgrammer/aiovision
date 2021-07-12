# Aiovision
**A Google Cloud Vision API demo using Python, aiogoogle, and asyncio**
****
Why use Google's SDKs when you could do *this*? Aiovision is an asyncio demo for Google Cloud Vision OCR based on [aiogoogle](https://aiogoogle.readthedocs.io/en/latest/).  

- Supports single file and batch text detection
- Asynchronous
- Automatic conversion to PDF for batch text detection

## Quickstart
If you have not already done so, [create a service account](https://cloud.google.com/iam/docs/creating-managing-service-accounts#creating), copy that service account's email address, [give it the *Storage Admin* role](https://cloud.google.com/iam/docs/granting-changing-revoking-access#access-control-via-console), and [generate and download a key in the json format](https://cloud.google.com/iam/docs/creating-managing-service-account-keys).

**Batch text detection example:**
```python
import aiovision, json, asyncio
with open("/path/to/creds.json") as creds, open("/path/to/pdf.pdf","rb") as pdf:
    session = aiovision.SessionManager(**json.load(creds))
    req = aiovision.detect_text_in_files_bulk(
        session,
        "my-globally-unique-bucket-name",
        [pdf, "/path/to/image.jpg"]
    )
    resp = asyncio.run(req)
```
*resp* will be in the form [{"responses": [[annotations](https://cloud.google.com/vision/docs/reference/rest/v1/AnnotateImageResponse),...]},...].

**Single file text detection example:**
```python
import aiovision, json, asyncio
with open("/path/to/creds.json") as creds:
    session = aiovision.SessionManager(**json.load(creds))
    req = aiovision.detect_text_in_file(
        session,
        "/path/to/another/image.jpg"
    )
    resp = asyncio.run(req)
```
*resp* will be in the form {"responses": [[annotations](https://cloud.google.com/vision/docs/reference/rest/v1/AnnotateImageResponse)]}.
****
# Pricing
Aiovision uses Cloud Vision's *Document Text Detection*, with pricing information available [here](https://cloud.google.com/vision/pricing). Aiovision also relies on Google Cloud Storage for batch request processing, with the pricing information for that service available [here](https://cloud.google.com/storage/pricing). However for most small use cases (less than a thousand requests per month), usage of these APIs will most likely be free.