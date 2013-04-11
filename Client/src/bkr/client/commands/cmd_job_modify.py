# -*- coding: utf-8 -*-

"""
bkr job-modify: Modify Beaker jobs
==================================

.. program:: bkr job-modify

Synopsis
--------

| :program:`bkr job-modify` [*options*] <taskspec>
|       [--response=<response>] [--retention-tag=<retention_tag>]
|       [--product=<product>]


Description
-----------


Specify one or more <taskspec> arguments to be modified.

Allows changing the response of a recipe set or job, or the retention tag 
and product of a job.

The <taskspec> arguments follow the same format as in other :program:`bkr` 
subcommands (for example, ``J:1234``). See :ref:`Specifying tasks <taskspec>` 
in :manpage:`bkr(1)`.

.. _job-modify-options:

Options
-------

.. option:: --response <response>

   Sets the response type of the job. Can be either 'ack' or 'nak'.

.. option:: --retention-tag <retention_tag>

   Sets the retention tag of a job. Must co-incide with correct product value.
   Please refer to the job page to see a list of available retention tags.

.. option:: --product <product>

   Sets the product of a job. Must co-incide with correct retention 
   tag value. Please refer to the job page to see a list of available 
   products.

Common :program:`bkr` options are described in the :ref:`Options 
<common-options>` section of :manpage:`bkr(1)`.

Exit status
-----------

Non-zero on error, otherwise zero.

Examples
--------

Set a recipe set to 'ack':

    bkr job-modify RS:1 --response ack

Set multiple jobs to be 'nak':

    bkr job-modify J:1 J:2 --response nak

Set a job's retention tag of 60days:

    bkr job-modify J:1 --retention-tag 60days

Set a job's product to validproduct and the audit retention tag:

   bkr job-modify J:1 --product validproduct --retention-tag audit

Unset a job's product and change to the scratch retention tag:

   bkr job-modify J:1 --retention-tag scratch --product=

See also
--------

:manpage:`bkr(1)`
"""
from bkr.client import BeakerCommand
from xmlrpclib import Fault
from sys import exit

class Job_Modify(BeakerCommand):
    """Modify certain job properties """

    enabled = True
    def options(self):
        self.parser.usage = "%%prog %s [options] <taskspec> ..." % self.normalized_name
        self.parser.add_option(
            "-r",
            "--response",
            help = "Set a job or recipesets response. Valid values are 'ack' or 'nak'",
         )

        self.parser.add_option(
            "-t",
            "--retention-tag",
            help = "Set a job's retention tag",
         )

        self.parser.add_option(
            "-p",
            "--product",
            help = "Set a job's product",
         )

    def run(self, *args, **kwargs):
        response = kwargs.pop('response', None)
        retention_tag = kwargs.pop('retention_tag', None)
        product = kwargs.pop('product', None)

        self.set_hub(**kwargs)
        self.check_taskspec_args(args, permitted_types=['J', 'RS'])
        modded = []
        error = False
        for job in args:
            try:
                if response:
                    self.hub.jobs.set_response(job, response)
                    modded.append(job)
                if retention_tag or product is not None:
                    self.hub.jobs.set_retention_product(job, retention_tag,
                        product,)
                    modded.append(job)
            except Fault, e:
                print str(e)
                error = True

        if modded:
            modded = set(modded)
            print 'Successfully modified jobs %s' % ' '.join(modded)
        else:
            print 'No jobs modified'

        if error:
            exit(1)
        else:
            exit(0)
