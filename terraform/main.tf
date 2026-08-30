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

resource "aws_instance" "api" {
  ami                    = "ami-0c02fb55956c7d316" # Amazon Linux 2 en us-east-1
  instance_type          = "t3.micro"
  key_name               = "isw-aws"
  vpc_security_group_ids = [aws_security_group.api.id]

  tags = {
    Name = "isw-api"
  }
}

output "public_ip" {
  description = "IP publica de la instancia"
  value       = aws_instance.api.public_ip
}
