# Lacework Dynamic Alerts

Lacework Dynamic Alerts allow you to update a policy's alert logic based on the results of a different query. This enhances Lacework's current alerting capabilities.

Rule-based alerts in Lacework are based on [LQL query](https://docs.lacework.net/lql/restricted/lql-overview)
logic that is applied to a [datasource](https://docs.lacework.net/lql/restricted/lql-overview). Alerts using datasources that contain activity logs e.g. (CloudTrailRawEvents, LW_ACT_GCP_ACTIVITY, LW_ACT_K8S_AUDIT) can only
reference the data in a specific log line of the activity log.

For instance, lacework-global-10 (S3 Bucket Deleted), alerts on all S3 buckets that are deleted. But what if you only wanted to alert on S3 buckets that are tagged with "Environment:Prod"?

This is impossible because because tagging information cannot be found in a Cloudtrail log line. 

```code
{
    "requestParameters": {
    "Host": "example-bucket.eu-central-1.amazonaws.com",
    "bucketName": "example-bucket"
    },
    "resources": [
    {
        "ARN": "arn:aws:s3:::example-bucket",
        "accountId": "xxx",
        "type": "AWS::S3::Bucket"
    }
}
```

The tags applied to ```example-bucket.eu-central-1.amazonaws.com``` can be found by querying ```LW_CFG_AWS_S3```, which returns the basic details of the bucket in under ```RESOURCE_TAGS```

```code
{
    "ACCOUNT_ALIAS": "",
    "ACCOUNT_ID": "xxx",
    "API_KEY": "list-buckets",
    "ARN": "arn:aws:s3:::example-bucket",
    "ORGANIZATION_ID": "",
    "PARENT_URN": null,
    "RESOURCE_CONFIG": {
      "CreationDate": "2024-08-20T18:22:24.000Z",
      "Name": "example-bucket"
    },
    "RESOURCE_ID": "example-bucket",
    "RESOURCE_KEY": "arn:aws:s3:::example-bucket",
    "RESOURCE_REGION": "eu-central-1",
    "RESOURCE_TAGS": {
      "Environment": "Prod"
    },
    "RESOURCE_TYPE": "s3:bucket",
    "SERVICE": "s3",
    "URN": "arn:aws:s3:::example-bucket"
  }
```

It's great that we can get the tagging data, but the issue is that currently you can't create a Cloudtrail policy/alert that uses a join between the activity logs and another datasource. This is the problem that Lacework Dynamic alerts looks to solve.

Working off of this example, we create the following LQL query to find all S3 buckets that have been tagged with Environment:Prod.

```yaml
queryId: LW_Custom_Get_All_S3_Tagged_Prod
queryText: |-
    {
        source {
            LW_CFG_AWS_S3
        }
        filter {
            UPPER(RESOURCE_TAGS:Environment) = 'PROD'
        }
        return distinct {
            ARN as resource_results 
        }
    }
```

> The query must return one field which is aliased as "resource_results"

The query that ```lacework-global-10``` (S3 Bucket Deleted) is based on is ```LW_Global_AWS_CTA_S3BucketDeleted```

```code
{
    source {
        CloudTrailRawEvents
    }
    filter {
        EVENT_SOURCE = 's3.amazonaws.com'
        and EVENT_NAME in ('DeleteBucket')
        and ERROR_CODE is null
    }
    return distinct {
        INSERT_ID,
        INSERT_TIME,
        EVENT_TIME,
        EVENT
    }
}
```

We'll modify the logic and add a placeholder for a variable:

```code
{
    source {
        CloudTrailRawEvents,
        array_to_rows(EVENT:resources) (bucket)
    }
    filter {
        EVENT_SOURCE = 's3.amazonaws.com'
        and EVENT_NAME in ('DeleteBucket')
        and ERROR_CODE is null
        and bucket:ARN in (${query_var})
    }
    return distinct {
        INSERT_ID,
        INSERT_TIME,
        EVENT_TIME,
        EVENT
    }
}
```

So the ```resource_results``` from our first query will be used to populate ```${query_var}``` on the 2nd.

Putting it all together we'll create a yaml file in the following format and place it in /alerts

```yaml
resource_query:
    queryId: LW_Custom_Get_All_S3_Tagged_Prod
    queryText: |-
        {
            source {
                LW_CFG_AWS_S3
            }
            filter {
                UPPER(RESOURCE_TAGS:Environment) = 'PROD'
            }
            return distinct {
                ARN as resource_results 
            }
        }

dynamic_query:
    queryId: LW_Custom_AWS_CTA_S3BucketDeleted_Prod_Tag_Only
    queryText: |-
        {
            source {
                CloudTrailRawEvents,
                array_to_rows(EVENT:resources) (bucket)
            }
            filter {
                EVENT_SOURCE = 's3.amazonaws.com'
                and EVENT_NAME in ('DeleteBucket')
                and ERROR_CODE is null
                and bucket:ARN in (${query_var})
            }
            return distinct {
                INSERT_ID,
                INSERT_TIME,
                EVENT_TIME,
                EVENT
            }
        }
```

> In order for the script to work, ```LW_Custom_AWS_CTA_S3BucketDeleted_Prod_Tag_Only``` must be added to Lacework and a policy must be created that references the query. More details can be found at: https://docs.lacework.net/cli/custom-policy-walkthrough-cli

> When initially adding adding the query ```LW_Custom_AWS_CTA_S3BucketDeleted_Prod_Tag_Only``` to Lacework the variable ```${query_var}``` cannot be present as it's not valid LQL. Instead add an empty single-quoted string in the ```in``` clause: ```IN ('')```:

```code
{
    source {
        CloudTrailRawEvents,
        array_to_rows(EVENT:resources) (bucket)
    }
    filter {
        EVENT_SOURCE = 's3.amazonaws.com'
        and EVENT_NAME in ('DeleteBucket')
        and ERROR_CODE is null
        and bucket:ARN IN ('') 
    }
    return distinct {
        INSERT_ID,
        INSERT_TIME,
        EVENT_TIME,
        EVENT
    }
}
```

# Configuring the Action
Add Actions secrets for interacting with the Lacework API:
![alt text](image.png)

Configure Lacework ```ACCOUNT``` in .github/workflows/main.yml:

```yaml
- name: execute py script # run main.py
        env:
          API_KEY: ${{ secrets.API_KEY }}
          API_SECRET: ${{ secrets.API_SECRET }}
          ACCOUNT: lwcs
```

Modify action cron as needed:

```yaml
on:
  schedule:
    - cron: '0 0 * * *' # every day at 00:00
  workflow_dispatch:  # Allows you to run the action manually
```
