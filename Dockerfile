# Use the Miniconda3 image as the base
FROM continuumio/miniconda3:latest

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user
RUN useradd -m -s /bin/bash conda_user

# Create and set the working directory
WORKDIR /home/conda_user/app

# Copy only the wrapper script
COPY ipython_wrapper.py .

# Install only the necessary packages for IPython execution
RUN conda install -y \
    ipython \
    matplotlib \
    numpy \
    pandas \
    scikit-learn \
    seaborn \
    scipy \
    statsmodels \
    plotly \
    basemap \
    && conda clean -afy

RUN pip install \
    yfinance \
    duckdb \
    imageio \
    nbformat


# Create images directory and set permissions
RUN mkdir -p /home/conda_user/app/images && \
    chown -R conda_user:conda_user /home/conda_user/app/images

# Change ownership of the working directory
RUN chown -R conda_user:conda_user /home/conda_user/app

# Switch to the non-root user
USER conda_user

# Set the entry point to wait for input
ENTRYPOINT ["python", "ipython_wrapper.py"]