// ---------------------------------------------------------------------------
// eventgrid.bicep — Event Grid System Topic for Storage Account events
// ---------------------------------------------------------------------------

@description('Name of the Event Grid System Topic.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('Resource ID of the Storage Account (event source).')
param storageAccountId string

@description('Name of the Function App hosting the ingest Event Grid trigger.')
param functionAppName string

@description('Name of the blob container watched for inbound dispute files.')
param ingestContainerName string = 'ingest'

@description('Name of the Event Grid subscription resource.')
param eventSubscriptionName string = 'ingest-blob-created'

// ---------------------------------------------------------------------------
// Event Grid System Topic
// ---------------------------------------------------------------------------
resource eventGridTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' = {
  name: name
  location: location
  tags: tags
  properties: {
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' existing = {
  name: functionAppName
}

resource ingestFunction 'Microsoft.Web/sites/functions@2023-12-01' existing = {
  parent: functionApp
  name: 'pl_ingest_raw_event'
}

resource eventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = {
  name: eventSubscriptionName
  parent: eventGridTopic
  properties: {
    eventDeliverySchema: 'EventGridSchema'
    destination: {
      endpointType: 'AzureFunction'
      properties: {
        resourceId: ingestFunction.id
        maxEventsPerBatch: 1
        preferredBatchSizeInKilobytes: 64
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
      ]
      subjectBeginsWith: '/blobServices/default/containers/${ingestContainerName}/blobs/'
      isSubjectCaseSensitive: false
    }
    retryPolicy: {
      maxDeliveryAttempts: 10
      eventTimeToLiveInMinutes: 1440
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output eventGridTopicName string = eventGridTopic.name
output eventGridTopicId string = eventGridTopic.id
output eventSubscriptionName string = eventSubscription.name
