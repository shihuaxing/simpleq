"""This module holds our queue abstractions."""


from boto.sqs import connect_to_region

from simpleq.jobs import Job


class Queue(object):
    """
    A representation of an Amazon SQS queue.

    There are two ways to create a Queue.

    1. Specify only a queue name, and connect to the default Amazon SQS region
       (*us-east-1*).  This will only work if you have your AWS credentials set
       appropriately in your environment (*``AWS_ACCESS_KEY_ID`` and
       ``AWS_SECRET_ACCESS_KEY``*).  To set your environment variables, you can
       use the shell command ``export``::

            $ export AWS_ACCESS_KEY_ID=xxx
            $ export AWS_SECRET_ACCESS_KEY=xxx

       You can then create a queue as follows::

            from simpleq.queues import Queue

            myqueue = Queue('myqueue')

    2. Specify a queue name, and a custom boto SQS connection.  For example::

            from boto.sqs import connect_to_region
            from simpleq.queues import Queue

            myqueue = Queue(
                'myqueue',
                connection = connect_to_region(
                    'us-west-1',
                    aws_access_key_id = 'blah',
                    aws_secret_access_key = 'blah'
                )
            )
    """
    BATCH_SIZE = 10
    WAIT_SECONDS = 20

    def __init__(self, name, connection=None):
        """
        Initialize an SQS queue.

        This will create a new boto SQS connection in the background, which will
        be used for all future queue requests.  This will speed up communication
        with SQS by taking advantage of boto's connection pooling functionality.

        :param str name: The name of the queue to use.
        :param obj connection: [optional] Either a boto connection object, or None.
        """
        self.name = name
        self.connection = connection or connect_to_region('us-east-1')
        self.queue = None

    def __repr__(self):
        """Print a human-friendly object representation."""
        return '<Queue({"name": "%s", "region": "%s"})>' % (
            self.name,
            self.connection.region.name,
        )

    @property
    def queue(self):
        """
        Handles lazy queue connections.

        If the specified queue doesn't exist, it will be created automatically.

        :returns: The SQS queue object.
        """
        if self._queue:
            return self._queue

        self._queue = self._connection.get_queue(self.name)
        if not self._queue:
            self._queue = self._connection.create_queue(self.name)

        return self._queue

    def delete(self):
        """Delete this SQS queue.

        This will remove all jobs in the queue, regardless of whether or not
        they're currently being processed.  This data cannot be recovered.
        """
        self._connection.delete_queue(self.queue)

    def add_job(self, job):
        """
        Add a new job to the queue.

        This will serialize the desired code, and dump it into the SQS queue.

        :param obj job: The Job to queue.
        """
        self.queue.write(job._message)

    def remove_job(self, job):
        """
        Remove a job from the queue.

        :param obj job: The Job to remove.
        """
        self.queue.delete_message(job._message)

    @property
    def jobs(self):
        """
        Return a list of existing jobs in the cheapest and quickest possible
        way.

        By default we will:

            - Use the maximum batch size to reduce calls to SQS.  This will
              reduce the cost of running the service, as less requests equals
              less dollars.

            - Wait for as long as possible (20 seconds) for a message to be
              sent to us (if none are in the queue already).  This way, we'll
              reduce our total request count, and spend less dollars.
        """
        jobs = []

        for message in self.queue.get_messages(
            num_messages = self.BATCH_SIZE,
            wait_time_seconds = self.WAIT_SECONDS,
        ):
            jobs.append(Job.from_message(message))

        return jobs
