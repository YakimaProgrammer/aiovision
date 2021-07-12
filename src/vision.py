from PIL import Image
import tempfile, asyncio, aiogoogle, logging, random, bucket

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

async def send_for_ocr(session, vision, request):
    req = vision.files.asyncBatchAnnotate()
    req.json = request
    
    try:
        return await session.as_service_account(req)
    except aiogoogle.excs.HTTPError as e:
        breakpoint()
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

async def detect_text_in_file(session, bucket_name, files, ocr_request = None, project_id = None, loop = None, executor = None):
    storage = await session.discover("storage","v1")
    vision = await session.discover("vision", "v1")
    
    if not project_id:
        project_id = session.service_account_creds.project_id
        
    obj_name = await bucket.upload_files_to_bucket_as_pdf(session, storage, bucket_name, project_id, files, loop, executor)

    if not ocr_request:
        ocr_request = build_basic_request(f"gs://{bucket_name}/{obj_name}", f"gs://{bucket_name}/{obj_name}-")

    resp = await send_for_ocr(session, vision, ocr_request)
        
    await wait_for_operation_to_be_complete(session, vision, resp["name"])
    output_name = f"{obj_name}-output-1-to-1.json"
    
    resp = await bucket.download_object(session, storage, bucket_name, output_name)

    #It actually takes the same amount of time to do this sequentially as it would with asyncio.gather
    await bucket.delete_object(session, storage, bucket_name, obj_name)
    await bucket.delete_object(session, storage, bucket_name, output_name)

    return resp
        
if __name__ == "__main__":
    import auth, json, asyncio

    with open("../google-apis-key.json") as f:
        session = auth.SessionManager(json.load(f))
        
    with open("C:/Users/magnu/Downloads/picture.jpg","rb") as f:
        resp = asyncio.run(detect_text_in_file(session, "magnusfulton-com-ocr", f))
