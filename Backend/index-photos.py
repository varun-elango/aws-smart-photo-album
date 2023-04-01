import json
import boto3
import time
import requests

esUrl = "https://search-photos-x265xwykkjszvgjbb6752wl2bi.us-east-1.es.amazonaws.com/photoalbum/_doc"


def lambda_handler(event, context):
    jsonBody = event['Records'][0]
    bucketName = jsonBody['s3']['bucket']['name']
    key = jsonBody['s3']['object']['key']
    reko = boto3.client('rekognition')
    s3 = boto3.client('s3')
    try:
        data = {}
        responses3 = s3.head_object(Bucket = bucketName, Key =key )
        
        response = reko.detect_labels(
            Image={'S3Object': {'Bucket': bucketName, 'Name': key}})
        data['objectKey'] = key
        data['bucket'] = bucketName
        data['createdTimestamp'] = time.time()
        data['labels'] = []
        print(responses3)
        if not responses3['Metadata'] =={}:
            customlabel = responses3['Metadata']['customlabels']
            if customlabel != "":
                data['labels'] = [i.strip() for i in customlabel.split(",")]
        
        for label in response['Labels']:
            if label['Confidence'] > 95:
                data['labels'].append(label['Name'])
        print(data['labels'])
        body = json.dumps(data)
        
        headers = {"Content-Type": "application/json"}
        r = requests.post(url=esUrl,auth = ('varun', 'Alpha*123'), data=body, headers=headers)
    except Exception as e:
        print("Error " + str(e))

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }