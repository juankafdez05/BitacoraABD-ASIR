# Guía de Instalación y Configuración Apache Cassandra (servidor) y cqlsh (cliente) en Debian 13

Esta guía cubre el procedimiento completo de instalación de Apache Cassandra 5.0 y `cqlsh` (cliente), la activación de la autenticación, la configuración de acceso remoto, la gestión básica de usuarios (roles) y las operaciones de creación de bases de datos (keyspaces y tablas), inserción y consulta de datos.

## 1. Servidor: Instalación de Cassandra y Configuración Inicial

### 1.1. Instalación de Java

Cassandra 5.0 requiere Java 11 o Java 17. Debido a que ninguno de los 2 esta disponible en trixie, tendremos que abilitar el repo externo de **Adoptium** para tener disponible OpenJDK 17.

```
sudo apt update
sudo apt install -y wget gnupg apt-transport-https ca-certificates
wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/adoptium.gpg > /dev/null
echo "deb https://packages.adoptium.net/artifactory/deb trixie  main" | sudo tee /etc/apt/sources.list.d/adoptium.list
sudo apt update
sudo apt install -y temurin-17-jdk

```
Ahora podemos comprobar que efectivamente tenemos java 17:

```
debian@cassandra:~$ java --version
openjdk 17.0.20.1 2026-08-18
OpenJDK Runtime Environment Temurin-17.0.20.1+1 (build 17.0.20.1+1)
OpenJDK 64-Bit Server VM Temurin-17.0.20.1+1 (build 17.0.20.1+1, mixed mode, sharing)
```


### 1.2. Añadir el Repositorio Oficial e Instalar Cassandra

Descargamos la clave de firma del proyecto y registramos el repositorio oficial de Apache. El nombre de distribución `50x` corresponde a la serie 5.0:

```
sudo mkdir -p /etc/apt/keyrings
sudo curl -fsSL -o /etc/apt/keyrings/apache-cassandra.asc https://downloads.apache.org/cassandra/KEYS
echo "deb [signed-by=/etc/apt/keyrings/apache-cassandra.asc] https://debian.cassandra.apache.org 50x main" | \
sudo tee /etc/apt/sources.list.d/cassandra.sources.list
sudo apt update
```

Comprobamos que el paquete `cassandra` se resuelve desde el repositorio de Apache e instalamos:

```
apt policy cassandra
sudo apt install -y cassandra
```

```
debian@cassandra:~$ apt-cache policy cassandra
debian@cassandra:~$ apt policy cassandra
cassandra:
  Installed: (none)
  Candidate: 5.0.9
  Version table:
     5.0.9 500
        500 https://debian.cassandra.apache.org 50x/main amd64 Packages
```

### 1.3. Arranque del Servicio

El paquete crea el usuario `cassandra`, el servicio de systemd y arranca el nodo automáticamente con la configuración por defecto (solo `localhost`). Comprobamos el estado del servicio y la versión instalada:

```
sudo systemctl status cassandra --no-pager
nodetool version
```

```
debian@cassandra:~$ sudo systemctl status cassandra --no-pager
● cassandra.service - LSB: distributed storage system for structured data
     Loaded: loaded (/etc/init.d/cassandra; generated)
     Active: active (running) since Thu 2026-10-08 17:53:17 UTC; 30s ago
 Invocation: c19cf127bcd14dcd8927f7a71df76e06
       Docs: man:systemd-sysv-generator(8)
    Process: 2093 ExecStart=/etc/init.d/cassandra start (code=exited, status=0/SUCCESS)
      Tasks: 54 (limit: 2317)
     Memory: 1.4G (peak: 1.4G)
        CPU: 10.607s
     CGroup: /system.slice/cassandra.service
             └─2210 /usr/bin/java -ea -da:net.openhft... -XX:+UseThreadPriorities -XX:+HeapDumpOnOutOfMemoryErro…

debian@cassandra:~$ nodetool version
ReleaseVersion: 5.0.9
```

> Cassandra tarda un rato en arrancar y hasta entonces `nodetool` puede responder con errores de conexión. Se puede seguir el arranque con `sudo tail -f /var/log/cassandra/system.log`.

Verificamos que el nodo está operativo (estado `UN` = *Up / Normal*):

```
nodetool status
```

```
debian@cassandra:~$ nodetool status
Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address    Load        Tokens  Owns (effective)  Host ID                               Rack
UN  127.0.0.1  114.72 KiB  16      100.0%            688e8c26-b95a-44ba-a8f7-c84d921caf3a  rack1
```

## 2. Servidor: Gestión Básica de Usuarios y Habilitación de Autenticación

Por defecto, Cassandra escucha únicamente en `localhost` y no requiere autenticación. En este paso se activa la autenticación y se crean los usuarios antes de abrir el servicio a la red. En Cassandra los usuarios son **roles**.

### 2.1. Habilitar Autenticación y Autorización

Editamos `/etc/cassandra/cassandra.yaml` para exigir usuario y contraseña (`PasswordAuthenticator`) y controlar permisos por rol (`CassandraAuthorizer`). Por defecto vienen como `AllowAllAuthenticator` y `AllowAllAuthorizer`, que permiten todo sin credenciales:

```
sudo sed -i 's/^authenticator:.*/authenticator: PasswordAuthenticator/' /etc/cassandra/cassandra.yaml
sudo sed -i 's/^authorizer:.*/authorizer: CassandraAuthorizer/' /etc/cassandra/cassandra.yaml
sudo systemctl restart cassandra
```

Verificamos la configuración aplicada:

```
grep -E '^(authenticator|authorizer):' /etc/cassandra/cassandra.yaml
```

```
grep -E '^(authenticator|authorizer):' /etc/cassandra/cassandra.yaml
authenticator: PasswordAuthenticator
authorizer: CassandraAuthorizer
```

### 2.2. Creación de Usuarios Administrador y de Aplicación

Tras activar la autenticación, el único acceso disponible es el superusuario por defecto `cassandra` / `cassandra`, que usamos una sola vez para crear los roles definitivos. Aprovecharemos y parte de nuestro nuevo administrador crearemos el usuario para la prueba.

```
cqlsh -u cassandra -p cassandra << 'EOF'
CREATE ROLE cassandraadmin WITH PASSWORD = '<PASSWORD_ADMIN>' AND SUPERUSER = true AND LOGIN = true;
CREATE ROLE usuario_prueba WITH PASSWORD = '<PASSWORD_APP>' AND LOGIN = true;
EOF
```

Con el nuevo administrador, inhabilitamos el superusuario por defecto para que sus credenciales conocidas no puedan utilizarse:

```
cqlsh -u cassandraadmin -p '<PASSWORD_ADMIN>' << 'EOF'
ALTER ROLE cassandra WITH SUPERUSER = false AND LOGIN = false;
EOF
```

Comprobamos los roles existentes:

```
cqlsh -u cassandraadmin -p '<PASSWORD_ADMIN>' -e "LIST ROLES;"
```
> Si no queremos escribir la contraseña en el terminal podemos quitar el parámetro -p para que nos la pida interactivamente.

```
debian@cassandra:~$ cqlsh -u cassandraadmin -p 'cassandraadmin' -e "LIST ROLES;"
Password:

 role           | super | login | options | datacenters
----------------+-------+-------+---------+-------------
      cassandra | False | False |        {} |         ALL
 cassandraadmin |  True |  True |        {} |         ALL
 usuario_prueba | False |  True |        {} |         ALL

(3 rows)
```

### 2.3. Modificación y Eliminación de Usuarios

Otras operaciones básicas de gestión de roles. Cambiar la contraseña de un usuario:

```
cqlsh -u cassandraadmin -p '<PASSWORD_ADMIN>' -e "ALTER ROLE usuario_prueba WITH PASSWORD = '<PASSWORD_APP>';"
```

Crear y eliminar un rol temporal, y comprobar el resultado:

```
cqlsh -u cassandraadmin -p '<PASSWORD_ADMIN>' -e "CREATE ROLE usuario_temporal WITH PASSWORD = '<PASSWORD_TEMP>' AND LOGIN = true;"
cqlsh -u cassandraadmin -p '<PASSWORD_ADMIN>' -e "DROP ROLE usuario_temporal;"
cqlsh -u cassandraadmin -p '<PASSWORD_ADMIN>' -e "LIST ROLES;"
```

```
debian@cassandra:~$ cqlsh -u cassandraadmin -p '<PASSWORD_ADMIN>' -e "LIST ROLES;"
[INSERTA AQUÍ LA SALIDA DEL COMANDO EN TU TERMINAL]
```

### 2.4. Habilitar el Acceso Remoto

Para el acceso de clientes intervienen estos parámetros de `/etc/cassandra/cassandra.yaml`:

- `rpc_address`: interfaz en la que se atiende a los **clientes CQL** (puerto 9042). Es la que debe abrirse a la red.
- `listen_address`: interfaz para la comunicación **entre nodos** (puerto 7000). Debe ser una IP concreta; no admite `0.0.0.0`.
- `seeds`: nodos de contacto para el arranque. En un único nodo, él mismo.

Indicamos la IP del servidor (muy importante, la IP del servidor Cassandra, no la del cliente) y reiniciamos:

```
sudo sed -i 's/^listen_address:.*/listen_address: TU_IP_SERVIDOR/' /etc/cassandra/cassandra.yaml
sudo sed -i 's/^rpc_address:.*/rpc_address: TU_IP_SERVIDOR/' /etc/cassandra/cassandra.yaml
sudo sed -i 's/- seeds: .*/- seeds: "TU_IP_SERVIDOR:7000"/' /etc/cassandra/cassandra.yaml
sudo systemctl restart cassandra
```

> No modifiques `cluster_name` una vez arrancado el nodo por primera vez: Cassandra guarda el nombre en sus datos y se negará a arrancar si no coincide con el del fichero.

Verificamos la configuración y la escucha en la red por el puerto 9042 (tras el reinicio puede tardar en aparecer):

```
grep -E '^(listen_address|rpc_address):|seeds:' /etc/cassandra/cassandra.yaml
sudo ss -tlnp | grep 9042
```

```
debian@cassandra:~$ grep -E '^(listen_address|rpc_address):|seeds:' /etc/cassandra/cassandra.yaml
      - seeds: "192.168.122.91:7000"
listen_address: 192.168.122.91
rpc_address: 192.168.122.91

debian@cassandra:~$ sudo ss -tlnp | grep 9042
debian@cassandra:~$ sudo ss -tlnp | grep 9042
LISTEN 0      4096   192.168.122.91:9042       0.0.0.0:*    users:(("java",pid=3545,fd=231))
```

Comprobamos que ya no se permite operar sin autenticación (se indica la IP, ya que `cqlsh` sin argumentos busca en `127.0.0.1`):

```
cqlsh TU_IP_SERVIDOR -e "DESCRIBE KEYSPACES;"
```

```
debian@cassandra:~$ cqlsh 192.168.122.91 -e "DESCRIBE KEYSPACES;"
Connection error: ('Unable to connect to any servers', {'192.168.122.91:9042': AuthenticationFailed('Remote end requires authentication')})
```

## 3. Cliente: Instalación y Conexión del Cliente Remoto

En el equipo cliente se instala únicamente `cqlsh`, sin instalar el servidor de Cassandra.

### 3.1. Instalación de `cqlsh` en el Cliente Remoto

En el repo de cassandra pra debian no se distribulle ningun paquete que traiga solo cqlsh separado del servidor, por lo que la opcion mas simple de instalarlo en el cliente es a traves de pipx.

```
sudo apt update
sudo apt install -y pipx
pipx ensurepath
pipx install cqlsh
```

Abre una nueva sesión de terminal (o ejecuta `source ~/.bashrc`) para que el comando esté en el `PATH` y verifica la versión:

```
cqlsh --version
```

```
debian@cliente:~$ cqlsh --version
cqlsh 6.2.2
```

> `cqlsh` depende de la versión de Python del sistema. Si el comando falla con errores de Python al arrancar, puede hacer falta usar una versión de `cqlsh` o de Python distinta.

### 3.2. Comprobación de Alcance de Red

Antes de autenticarnos, verificamos que el puerto del servidor es alcanzable desde el cliente:

```
nc -zv TU_IP_SERVIDOR 9042
```

```
debian@cliente:~$ nc -zv TU_IP_SERVIDOR 9042
nc -zv 192.168.122.91 9042
Connection to 192.168.122.91 9042 port [tcp/*] succeeded!
```

> Si `nc` no está disponible: `sudo apt install -y netcat-openbsd`.

### 3.3. Conexión Remota al Servidor

Nos conectamos desde la máquina cliente hacia la base de datos remota utilizando el usuario autenticado:

```
cqlsh TU_IP_SERVIDOR 9042 -u usuario_prueba
```

Una vez dentro de la shell, podemos verificar el estado de la conexión consultando la información del clúster:

```
SELECT cluster_name, release_version FROM system.local;
```

```
cqlsh 192.168.122.91 9042 -u usuario_prueba
Password:
WARNING: cqlsh was built against 5.0.0, but this server is 5.0.9.  All features may not work!

ATTENTION: All commands will be saved to history file: /home/alfre/.cassandra/cqlsh_history
This may include sensitive information such as passwords.
To disable history, use --disable-history or set 'disabled = true' in the [history] section of cqlshrc.
See https://cassandra.apache.org/doc/latest/tools/cqlsh.html for more information.

Connected to Test Cluster at 192.168.122.91:9042
[cqlsh 6.2.2 | Cassandra 5.0.9 | CQL spec 3.4.7 | Native protocol v5]
Use HELP for help.
usuario_prueba@cqlsh> SELECT cluster_name, release_version FROM system.local;

 cluster_name | release_version
--------------+-----------------
 Test Cluster |           5.0.9

(1 rows)
usuario_prueba@cqlsh>
```
