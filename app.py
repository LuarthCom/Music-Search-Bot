from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from flask_socketio import SocketIO, emit
import os
import uuid
import threading
from werkzeug.utils import secure_filename
import pandas as pd
from src.music_search_bot import run_playlist

app = Flask(__name__)
app.config['SECRET_KEY'] = 'music_search_secret_key_2024'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
socketio = SocketIO(app, cors_allowed_origins="*")

# Armazenamento em memória para jobs
jobs = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_job():
    try:
        # Validação do arquivo
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Arquivo deve ser CSV'}), 400
        
        # Parâmetros
        delay = float(request.form.get('delay', 1.5))
        max_retries = int(request.form.get('max_retries', 3))
        concurrency = int(request.form.get('concurrency', 2))
        
        # Validação de parâmetros
        if delay < 0.1 or delay > 10:
            return jsonify({'error': 'Delay deve estar entre 0.1 e 10 segundos'}), 400
        if max_retries < 1 or max_retries > 10:
            return jsonify({'error': 'Max retries deve estar entre 1 e 10'}), 400
        if concurrency < 1 or concurrency > 3:
            return jsonify({'error': 'Concorrência deve estar entre 1 e 3'}), 400
        
        # Gera job ID
        job_id = str(uuid.uuid4())
        
        # Salva arquivo
        filename = secure_filename(file.filename)
        base_name = filename.rsplit('.', 1)[0]
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        file.save(input_path)
        
        # Validação do CSV
        try:
            df = pd.read_csv(input_path, encoding='utf-8')
            columns = df.columns.tolist()
            
            has_exportify = 'Track Name' in columns and 'Artist Name(s)' in columns
            has_manual = 'Música' in columns and 'Artista' in columns
            
            if not (has_exportify or has_manual):
                os.remove(input_path)
                return jsonify({
                    'error': 'CSV deve conter colunas "Track Name" e "Artist Name(s)" ou "Música" e "Artista"'
                }), 400
                
        except Exception as e:
            if os.path.exists(input_path):
                os.remove(input_path)
            return jsonify({'error': f'Erro ao ler CSV: {str(e)}'}), 400
        
        # Caminhos de saída
        output_csv = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{base_name}_com_links.csv")
        output_xlsx = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{base_name}_com_links.xlsx")
        
        # Inicializa job
        jobs[job_id] = {
            'status': 'running',
            'progress': 0,
            'current': 0,
            'total': len(df),
            'stats': {'total_songs': 0, 'youtube_found': 0, 'fourshared_found': 0, 'not_found': 0, 'errors': 0},
            'last_message': 'Iniciando...',
            'input_path': input_path,
            'output_csv': output_csv,
            'output_xlsx': output_xlsx,
            'base_name': base_name
        }
        
        # Inicia processamento em thread
        thread = threading.Thread(
            target=process_playlist,
            args=(job_id, input_path, output_csv, output_xlsx, delay, max_retries, concurrency)
        )
        thread.daemon = True
        thread.start()
        
        return redirect(url_for('progress', job_id=job_id))
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

def process_playlist(job_id, input_path, output_csv, output_xlsx, delay, max_retries, concurrency):
    try:
        def progress_callback(current, total, stats, last_message):
            progress = int((current / total) * 100)
            jobs[job_id].update({
                'progress': progress,
                'current': current,
                'total': total,
                'stats': stats,
                'last_message': last_message
            })
            
            socketio.emit('progress_update', {
                'pct': progress,
                'current': current,
                'total': total,
                'stats': stats,
                'last': last_message
            }, room=f"progress_{job_id}")
        
        # Executa processamento
        final_stats = run_playlist(
            input_path, output_csv, output_xlsx,
            delay, max_retries, concurrency,
            progress_callback
        )
        
        # Finaliza job
        jobs[job_id].update({
            'status': 'completed',
            'progress': 100,
            'stats': final_stats
        })
        
        socketio.emit('job_completed', {
            'stats': final_stats
        }, room=f"progress_{job_id}")
        
    except Exception as e:
        jobs[job_id].update({
            'status': 'error',
            'error': str(e)
        })
        
        socketio.emit('job_error', {
            'error': str(e)
        }, room=f"progress_{job_id}")

# Nova API para polling
@app.route('/api/job/<job_id>/status')
def job_status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job não encontrado'}), 404
    
    job = jobs[job_id]
    return jsonify({
        'status': job['status'],
        'progress': job['progress'],
        'current': job['current'],
        'total': job['total'],
        'stats': job['stats'],
        'last_message': job['last_message']
    })

@app.route('/progress/<job_id>')
def progress(job_id):
    if job_id not in jobs:
        return redirect(url_for('index'))
    
    job = jobs[job_id]
    return render_template('progress.html', job_id=job_id, job=job)

@app.route('/results/<job_id>')
def results(job_id):
    if job_id not in jobs:
        return redirect(url_for('index'))
    
    job = jobs[job_id]
    if job['status'] != 'completed':
        return redirect(url_for('progress', job_id=job_id))
    
    return render_template('results.html', job_id=job_id, job=job)

@app.route('/download/<job_id>')
def download(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job não encontrado'}), 404
    
    job = jobs[job_id]
    if job['status'] != 'completed':
        return jsonify({'error': 'Job não finalizado'}), 400
    
    file_type = request.args.get('type', 'csv')
    
    if file_type == 'csv':
        file_path = job['output_csv']
        filename = f"{job['base_name']}_com_links.csv"
    elif file_type == 'xlsx':
        file_path = job['output_xlsx']
        filename = f"{job['base_name']}_com_links.xlsx"
    else:
        return jsonify({'error': 'Tipo de arquivo inválido'}), 400
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'Arquivo não encontrado'}), 404
    
    return send_file(file_path, as_attachment=True, download_name=filename)

@socketio.on('join_progress')
def on_join_progress(data):
    job_id = data['job_id']
    if job_id in jobs:
        room = f"progress_{job_id}"
        socketio.server.enter_room(request.sid, room)
        
        # Envia estado atual
        job = jobs[job_id]
        emit('progress_update', {
            'pct': job['progress'],
            'current': job['current'],
            'total': job['total'],
            'stats': job['stats'],
            'last': job['last_message']
        })

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    import eventlet
    socketio.run(app, host="0.0.0.0", port=8000)

