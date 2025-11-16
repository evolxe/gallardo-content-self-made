Setup in Linux

Install Python 
To install Python 3.10 on a Linux system (typically Ubuntu or Debian-based), you have two main methods:
Install from the official package repository (if available):
Update package lists:
text
sudo apt update


Install Python 3.10:
text
sudo apt install python3.10


Verify the installation:
text
python3.10 --version


Install by compiling from source (if you want a specific subversion or your distro doesn't have 3.10 in repo):
Download the source tarball from python.org, e.g.:
text
wget https://www.python.org/ftp/python/3.10.16/Python-3.10.16.tgz


Extract it:
text
tar -xzf Python-3.10.16.tgz
cd Python-3.10.16


Prepare for compilation with optimizations:
text
sudo ./configure --enable-optimizations


Compile using all CPU cores:
text
sudo make -j $(nproc)


Install without overwriting existing Python versions:
text
sudo make altinstall


Verify installation:
text
python3.10 --version


This ensures Python 3.10 is installed alongside existing versions without interference. This method also installs pip for Python 3.10.
For Ubuntu systems, adding the deadsnakes PPA repository may help if Python 3.10 is not available by default.
These steps apply to Debian, Ubuntu, and closely related Linux distributions. Adjustments may be needed for other distros.
Let me know if you want commands tailored for a specific Linux distribution or additional help with setup after installation!linux.how2shout+2​
https://linux.how2shout.com/how-to-install-python-3-10-on-ubuntu-24-04-22-04-20-04/
https://tecadmin.net/how-to-install-python-3-10-on-ubuntu-debian-linuxmint/
https://tutorpython.com/install-python-3-10-on-ubuntu-22-04
https://computingforgeeks.com/how-to-install-python-on-ubuntu-linux-system/
https://gist.github.com/rutcreate/c0041e842f858ceb455b748809763ddb
https://www.geeksforgeeks.org/python/how-to-install-python-on-linux/
https://stackoverflow.com/questions/72332529/add-python-3-10-on-ubuntu
https://www.educative.io/answers/how-to-install-a-specific-python-version-in-linux
https://www.python.org/downloads/release/python-3100/
https://www.reddit.com/r/AlmaLinux/comments/1gq8fs0/install_specific_version_of_python/
Install git
To install Git on Debian 13, perform the following steps:
Update your package list: Open your terminal and run the following command to ensure your system's package list is up-to-date:
Code
   sudo apt update
Install Git: Install the Git package using apt:
Code
   sudo apt install git
You may be prompted to confirm the installation by typing Y and pressing Enter.
Verify the installation: After the installation completes, verify that Git is installed correctly by checking its version:
Code
   git --version
This command should display the installed Git version, confirming a successful installation.
Configure Git (optional but recommended): Set your global Git username and email address. These details will be associated with your commits. Replace "Your Name" and "your.email@example.com" with your actual name and email:
Code
   git config --global user.name "Your Name"
   git config --global user.email "your.email@example.com"
To view your current Git configuration, use:
Code
   git config --list




When all that fails, use a token
The error message "Password authentication is not supported for Git operations" indicates that GitHub no longer supports using a GitHub account password for HTTPS Git operations like clone, push, or pull. Instead, GitHub requires use of a personal access token (PAT) or SSH key authentication.
To resolve this error when cloning your repository via HTTPS, here are the steps you can take:
Use a Personal Access Token (PAT)
Generate a personal access token on GitHub:
Go to your GitHub account settings.
Navigate to Developer Settings > Personal Access Tokens > Tokens (classic).
Click "Generate new token (classic)".
Select appropriate scopes (usually repo for full control of private repositories).
Generate and copy the token.
Use the PAT as the password when prompted:
When you run git clone and it prompts for username, enter your GitHub username.
When it prompts for password, paste in the PAT instead of your actual GitHub password.





Clone the Repository
Cmd: Git clone https://github.com/ROCstudios/gallardo-automated-content-pipeline.git
Enter personal github username 
Enter the token from the above process as the password



Setup to run scripts
Go to projects/g… 
Cmd: git pull
Username: davidwkleber
Token for password: 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


Put Python in $PATH
To add to $PATH permanently
You can make the change permanent for your user by editing the ~/.bashrc file. 
Open your terminal.
Open the ~/.bashrc file in a text editor (like nano):
bash
nano ~/.bashrc


Scroll to the end of the file and add the following line, replacing /new/path with the directory you want to add:
bash
export PATH="$PATH:/home/videoeditor/Python-3.10.16/python"


Save the file and exit the editor.
To apply the changes immediately, run the source command:
bash
source ~/.bashrc


Install missing packages:
Requests
Gspread
numpy
moviepy




Here are the steps to create and use a virtual environment with Python 3.13:
Navigate to your project directory:
bash
cd ~/projects/gallardo-automated-content-pipeline


Create a virtual environment (called venv here):
bash
python3 -m venv venv


Activate the virtual environment:
bash
source venv/bin/activate


After activation, your shell prompt will typically show (venv) to indicate the environment is active.
Now install the requests package inside this virtual environment using pip:
bash
pip install requests


Use Python normally in this virtual environment. When done, you can deactivate it by:
bash
Deactivate
Then run the script in the virtual environment
./venv/bin/python sheet.py





Install Git CLI
(type -p wget >/dev/null || (sudo apt update && sudo apt install wget -y)) \
	&& sudo mkdir -p -m 755 /etc/apt/keyrings \
	&& out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
	&& cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
	&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
	&& sudo mkdir -p -m 755 /etc/apt/sources.list.d \
	&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
	&& sudo apt update \
	&& sudo apt install gh -y

Install our code
 git clone https://github.com/ROCstudios/gallardo-automated-content-pipeline.git


Posting

Fonts

Install the client font

Sudo cp MinionPro-Regular.otf /usr/share/fonts

Install the font manager

sudo apt-get install fontconfig

Sudo fc-cache -fv
