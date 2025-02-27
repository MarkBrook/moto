from __future__ import unicode_literals
import boto.ec2
import boto.ec2.autoscale
import boto.ec2.elb
import boto3
import sure
from boto3 import Session

from moto import mock_ec2_deprecated, mock_autoscaling_deprecated, mock_elb_deprecated
from moto import mock_autoscaling, mock_ec2, mock_elb

from moto.ec2 import ec2_backends
from tests import EXAMPLE_AMI_ID, EXAMPLE_AMI_ID2


def test_use_boto_regions():
    boto_regions = set()
    for region in Session().get_available_regions("ec2"):
        boto_regions.add(region)
    for region in Session().get_available_regions("ec2", partition_name="aws-us-gov"):
        boto_regions.add(region)
    for region in Session().get_available_regions("ec2", partition_name="aws-cn"):
        boto_regions.add(region)
    moto_regions = set(ec2_backends)

    moto_regions.should.equal(boto_regions)


def add_servers_to_region(ami_id, count, region):
    conn = boto.ec2.connect_to_region(region)
    for index in range(count):
        conn.run_instances(ami_id)


def add_servers_to_region_boto3(ami_id, count, region):
    ec2 = boto3.resource("ec2", region_name=region)
    ec2.create_instances(ImageId=ami_id, MinCount=count, MaxCount=count)


# Has boto3 equivalent
@mock_ec2_deprecated
def test_add_servers_to_a_single_region():
    region = "ap-northeast-1"
    add_servers_to_region(EXAMPLE_AMI_ID, 1, region)
    add_servers_to_region(EXAMPLE_AMI_ID2, 1, region)

    conn = boto.ec2.connect_to_region(region)
    reservations = conn.get_all_reservations()
    len(reservations).should.equal(2)

    image_ids = [r.instances[0].image_id for r in reservations]
    image_ids.should.equal([EXAMPLE_AMI_ID, EXAMPLE_AMI_ID2])


@mock_ec2
def test_add_servers_to_a_single_region_boto3():
    region = "ap-northeast-1"
    add_servers_to_region_boto3(EXAMPLE_AMI_ID, 1, region)
    add_servers_to_region_boto3(EXAMPLE_AMI_ID2, 1, region)

    client = boto3.client("ec2", region_name=region)
    reservations = client.describe_instances()["Reservations"]
    reservations.should.have.length_of(2)

    image_ids = [r["Instances"][0]["ImageId"] for r in reservations]
    image_ids.should.equal([EXAMPLE_AMI_ID, EXAMPLE_AMI_ID2])


# Has boto3 equivalent
@mock_ec2_deprecated
def test_add_servers_to_multiple_regions():
    region1 = "us-east-1"
    region2 = "ap-northeast-1"
    add_servers_to_region(EXAMPLE_AMI_ID, 1, region1)
    add_servers_to_region(EXAMPLE_AMI_ID2, 1, region2)

    us_conn = boto.ec2.connect_to_region(region1)
    ap_conn = boto.ec2.connect_to_region(region2)
    us_reservations = us_conn.get_all_reservations()
    ap_reservations = ap_conn.get_all_reservations()

    len(us_reservations).should.equal(1)
    len(ap_reservations).should.equal(1)

    us_reservations[0].instances[0].image_id.should.equal(EXAMPLE_AMI_ID)
    ap_reservations[0].instances[0].image_id.should.equal(EXAMPLE_AMI_ID2)


@mock_ec2
def test_add_servers_to_multiple_regions_boto3():
    region1 = "us-east-1"
    region2 = "ap-northeast-1"
    add_servers_to_region_boto3(EXAMPLE_AMI_ID, 1, region1)
    add_servers_to_region_boto3(EXAMPLE_AMI_ID2, 1, region2)

    us_client = boto3.client("ec2", region_name=region1)
    ap_client = boto3.client("ec2", region_name=region2)
    us_reservations = us_client.describe_instances()["Reservations"]
    ap_reservations = ap_client.describe_instances()["Reservations"]

    us_reservations.should.have.length_of(1)
    ap_reservations.should.have.length_of(1)

    us_reservations[0]["Instances"][0]["ImageId"].should.equal(EXAMPLE_AMI_ID)
    ap_reservations[0]["Instances"][0]["ImageId"].should.equal(EXAMPLE_AMI_ID2)


# Has boto3 equivalent
@mock_autoscaling_deprecated
@mock_elb_deprecated
def test_create_autoscaling_group():
    elb_conn = boto.ec2.elb.connect_to_region("us-east-1")
    elb_conn.create_load_balancer(
        "us_test_lb", zones=[], listeners=[(80, 8080, "http")]
    )
    elb_conn = boto.ec2.elb.connect_to_region("ap-northeast-1")
    elb_conn.create_load_balancer(
        "ap_test_lb", zones=[], listeners=[(80, 8080, "http")]
    )

    us_conn = boto.ec2.autoscale.connect_to_region("us-east-1")
    config = boto.ec2.autoscale.LaunchConfiguration(
        name="us_tester", image_id=EXAMPLE_AMI_ID, instance_type="m1.small"
    )
    x = us_conn.create_launch_configuration(config)

    us_subnet_id = list(ec2_backends["us-east-1"].subnets["us-east-1c"].keys())[0]
    ap_subnet_id = list(
        ec2_backends["ap-northeast-1"].subnets["ap-northeast-1a"].keys()
    )[0]
    group = boto.ec2.autoscale.AutoScalingGroup(
        name="us_tester_group",
        availability_zones=["us-east-1c"],
        default_cooldown=60,
        desired_capacity=2,
        health_check_period=100,
        health_check_type="EC2",
        max_size=2,
        min_size=2,
        launch_config=config,
        load_balancers=["us_test_lb"],
        placement_group="us_test_placement",
        vpc_zone_identifier=us_subnet_id,
        termination_policies=["OldestInstance", "NewestInstance"],
    )
    us_conn.create_auto_scaling_group(group)

    ap_conn = boto.ec2.autoscale.connect_to_region("ap-northeast-1")
    config = boto.ec2.autoscale.LaunchConfiguration(
        name="ap_tester", image_id=EXAMPLE_AMI_ID, instance_type="m1.small"
    )
    ap_conn.create_launch_configuration(config)

    group = boto.ec2.autoscale.AutoScalingGroup(
        name="ap_tester_group",
        availability_zones=["ap-northeast-1a"],
        default_cooldown=60,
        desired_capacity=2,
        health_check_period=100,
        health_check_type="EC2",
        max_size=2,
        min_size=2,
        launch_config=config,
        load_balancers=["ap_test_lb"],
        placement_group="ap_test_placement",
        vpc_zone_identifier=ap_subnet_id,
        termination_policies=["OldestInstance", "NewestInstance"],
    )
    ap_conn.create_auto_scaling_group(group)

    len(us_conn.get_all_groups()).should.equal(1)
    len(ap_conn.get_all_groups()).should.equal(1)

    us_group = us_conn.get_all_groups()[0]
    us_group.name.should.equal("us_tester_group")
    list(us_group.availability_zones).should.equal(["us-east-1c"])
    us_group.desired_capacity.should.equal(2)
    us_group.max_size.should.equal(2)
    us_group.min_size.should.equal(2)
    us_group.vpc_zone_identifier.should.equal(us_subnet_id)
    us_group.launch_config_name.should.equal("us_tester")
    us_group.default_cooldown.should.equal(60)
    us_group.health_check_period.should.equal(100)
    us_group.health_check_type.should.equal("EC2")
    list(us_group.load_balancers).should.equal(["us_test_lb"])
    us_group.placement_group.should.equal("us_test_placement")
    list(us_group.termination_policies).should.equal(
        ["OldestInstance", "NewestInstance"]
    )

    ap_group = ap_conn.get_all_groups()[0]
    ap_group.name.should.equal("ap_tester_group")
    list(ap_group.availability_zones).should.equal(["ap-northeast-1a"])
    ap_group.desired_capacity.should.equal(2)
    ap_group.max_size.should.equal(2)
    ap_group.min_size.should.equal(2)
    ap_group.vpc_zone_identifier.should.equal(ap_subnet_id)
    ap_group.launch_config_name.should.equal("ap_tester")
    ap_group.default_cooldown.should.equal(60)
    ap_group.health_check_period.should.equal(100)
    ap_group.health_check_type.should.equal("EC2")
    list(ap_group.load_balancers).should.equal(["ap_test_lb"])
    ap_group.placement_group.should.equal("ap_test_placement")
    list(ap_group.termination_policies).should.equal(
        ["OldestInstance", "NewestInstance"]
    )


@mock_autoscaling
@mock_elb
@mock_ec2
def test_create_autoscaling_group_boto3():
    regions = [("us-east-1", "c"), ("ap-northeast-1", "a")]
    for region, zone in regions:
        a_zone = "{}{}".format(region, zone)
        asg_name = "{}_tester_group".format(region)
        lb_name = "{}_lb".format(region)
        config_name = "{}_tester".format(region)

        elb_client = boto3.client("elb", region_name=region)
        elb_client.create_load_balancer(
            LoadBalancerName=lb_name,
            Listeners=[
                {"Protocol": "http", "LoadBalancerPort": 80, "InstancePort": 8080}
            ],
            AvailabilityZones=[],
        )

        as_client = boto3.client("autoscaling", region_name=region)
        as_client.create_launch_configuration(
            LaunchConfigurationName=config_name,
            ImageId=EXAMPLE_AMI_ID,
            InstanceType="m1.small",
        )

        ec2_client = boto3.client("ec2", region_name=region)
        subnet_id = ec2_client.describe_subnets(
            Filters=[{"Name": "availability-zone", "Values": [a_zone]}]
        )["Subnets"][0]["SubnetId"]

        as_client.create_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            AvailabilityZones=[a_zone],
            DefaultCooldown=60,
            DesiredCapacity=2,
            HealthCheckGracePeriod=100,
            HealthCheckType="EC2",
            LaunchConfigurationName=config_name,
            LoadBalancerNames=[lb_name],
            MinSize=2,
            MaxSize=2,
            PlacementGroup="us_test_placement",
            VPCZoneIdentifier=subnet_id,
            TerminationPolicies=["OldestInstance", "NewestInstance"],
        )

        groups = as_client.describe_auto_scaling_groups()["AutoScalingGroups"]
        groups.should.have.length_of(1)
        group = groups[0]

        group["AutoScalingGroupName"].should.equal(asg_name)
        group["DesiredCapacity"].should.equal(2)
        group["MaxSize"].should.equal(2)
        group["MinSize"].should.equal(2)
        group["VPCZoneIdentifier"].should.equal(subnet_id)
        group["LaunchConfigurationName"].should.equal(config_name)
        group["DefaultCooldown"].should.equal(60)
        group["HealthCheckGracePeriod"].should.equal(100)
        group["HealthCheckType"].should.equal("EC2")
        group["LoadBalancerNames"].should.equal([lb_name])
        group["PlacementGroup"].should.equal("us_test_placement")
        group["TerminationPolicies"].should.equal(["OldestInstance", "NewestInstance"])
