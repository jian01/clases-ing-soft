terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1" # credenciales: ~/.aws
}

resource "aws_security_group" "api" {
  name        = "isw-api"
  description = "Security group for ISW API"

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "isw-api"
  }
}

resource "aws_iam_role" "grafana_cloudwatch" {
  name = "grafana-cloudwatch-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "grafana-cloudwatch-role"
  }
}

resource "aws_iam_role_policy_attachment" "cloudwatch_readonly" {
  role       = aws_iam_role.grafana_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess"
}

resource "aws_iam_instance_profile" "grafana_cloudwatch" {
  name = "grafana-cloudwatch-profile"
  role = aws_iam_role.grafana_cloudwatch.name
}

resource "aws_key_pair" "isw" {
  key_name   = "isw-aws"
  public_key = file("~/.ssh/isw-aws.pem.pub")

  tags = {
    Name = "isw-aws"
  }
}

resource "aws_instance" "api" {
  ami                    = "ami-0c7217cdde317cfec" # Ubuntu 22.04 en us-east-1
  instance_type          = "t3.micro"
  key_name               = aws_key_pair.isw.key_name
  vpc_security_group_ids = [aws_security_group.api.id]
  iam_instance_profile   = aws_iam_instance_profile.grafana_cloudwatch.name

  tags = {
    Name = "isw-api"
  }
}

output "public_ip" {
  description = "IP publica de la instancia"
  value       = aws_instance.api.public_ip
}
