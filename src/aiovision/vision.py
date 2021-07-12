from PIL import Image
import tempfile, asyncio, aiogoogle, logging, random, base64
from . import bucket, preprocess

def build_basic_request(gs_file_uri, destination_bucket, features="DOCUMENT_TEXT_DETECTION", batch_size=100):
    return {
        "requests": [
            {
                "inputConfig": {
                    "gcsSource": {
                        "uri": gs_file_uri
                    },
                    "mimeType": "application/pdf"
                },
                "features": [
                    {
                        "type": features
                    }
                ],
                "outputConfig": {
                    "gcsDestination": {
                        "uri": destination_bucket
                    },
                    "batchSize": batch_size
                }
            }
        ]
    }

def build_basic_sync_request(base64_data, features="DOCUMENT_TEXT_DETECTION"):
    return {
        "requests": [
            {
                "image": {
                    "content": base64_data
                },
                "features": [
                    {
                        "type": features
                    }
                ]
            }
        ]
    }

async def send_for_ocr(session, vision, request, sync = False):
    if sync:
        req = vision.images.annotate()
    else:
        req = vision.files.asyncBatchAnnotate()
    req.json = request
    
    try:
        return await session.as_service_account(req)
    except aiogoogle.excs.HTTPError as e:
        logging.exception("Unable to submit ocr task")
        
async def wait_for_operation_to_be_complete(session, vision, name, polling_interval=1):
    name = "/".join(name.split("/")[-2:]) #projects/my-google-apis-project-123/operation/123456789abcdef -> operation/123456789abcdef

    running = True
    while running:
        await asyncio.sleep(polling_interval)
        try:
            req = vision.operations.get(name=name)
            #It tries to be helpful and encode slash charecters automatically
            #Usually that is what you want.
            #But not in this case
            req.url = req.url.replace("%2F","/")
            resp = await session.as_service_account(req)
            
            if resp["metadata"]["state"] == "DONE":
                running = False
            
        except aiogoogle.excs.HTTPError:
            logging.exception("Unable to poll ocr task for completion")

async def detect_text_in_files_bulk(session, bucket_name, files, ocr_request = None, project_id = None, loop = None, executor = None):
    storage = await session.discover("storage","v1")
    vision = await session.discover("vision", "v1")
    
    if not project_id:
        project_id = session.service_account_creds.project_id
        
    obj_name = await bucket.upload_files_to_bucket_as_pdf(session, storage, bucket_name, project_id, files, loop, executor)

    if not ocr_request:
        ocr_request = build_basic_request(f"gs://{bucket_name}/{obj_name}", f"gs://{bucket_name}/{obj_name}-")

    resp = await send_for_ocr(session, vision, ocr_request)
        
    await wait_for_operation_to_be_complete(session, vision, resp["name"])

    output_files = await bucket.get_output_files(session, storage, bucket_name, obj_name)

    resp = await asyncio.gather(*(bucket.download_object(session, storage, bucket_name, name) for name in output_files))

    await asyncio.gather(
        bucket.delete_object(session, storage, bucket_name, obj_name),
        *(bucket.delete_object(session, storage, bucket_name, name) for name in output_files)
    )
    
    return resp

async def detect_text_in_file(session, f, ocr_request = None):
    vision = await session.discover("vision", "v1")
    
    try:
        f.seek(0)
        base64_data = base64.b64encode(f.read()).decode()        
    except AttributeError:
        with open(f,"rb") as f_asfile:
            base64_data = base64.b64encode(f_asfile.read()).decode()
    
    if not ocr_request:
        ocr_request = build_basic_sync_request(base64_data)

    return await send_for_ocr(session, vision, ocr_request, True)
