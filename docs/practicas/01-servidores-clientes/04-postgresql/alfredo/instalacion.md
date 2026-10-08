# Instalación de PostgreSQL(Servidor y Cliente) en Debian 13 y Conexión de Clientes Remotos (Por Alfredo)

Esta guía describe el procedimiento para instalar PostgreSQL en Debian 13 (Trixie), configurarlo para aceptar conexiones desde otros equipos de la red y preparar un cliente remoto que se conecte a él.

---

## 1. Servidor: Instalación de PostgreSQL

Instalamos el servidor desde los repositorios oficiales de Debian (en Debian 13 la versión por defecto es la 17):

```
sudo apt update
sudo apt install -y postgresql
```

Comprobamos la versión instalada, que el servicio está activo y habilitado en el arranque, y que el clúster está en línea:

```
psql --version
sudo systemctl status postgresql --no-pager
pg_lsclusters
```

```
debian@postgres:~$ psql --version
psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1)
debian@postgres:~$ sudo systemctl status postgresql --no-pager
● postgresql.service - PostgreSQL RDBMS
     Loaded: loaded (/usr/lib/systemd/system/postgresql.service; enabled; preset: enabled)
     Active: active (exited) since Thu 2026-10-08 16:04:20 UTC; 2min 21s ago
 Invocation: 894a0b37de854448a6196b8d6bc3b9a7
   Main PID: 2677 (code=exited, status=0/SUCCESS)
   Mem peak: 2M
        CPU: 5ms

debian@postgres:~$ pg_lsclusters
Ver Cluster Port Status Owner    Data directory              Log file
17  main    5432 online postgres /var/lib/postgresql/17/main /var/log/postgresql/postgresql-17-main.log
```

## 2. Servidor: Configuración para Escuchar en Red

Para permitir clientes remotos, debemos tocar 2 ficheros en la ruta `/etc/postgresql/17/main/` . Por un lado **postgresql.conf** para permitir que postgres escuche las peticiones y por otro **pg_hba.conf** para permitir la autenticación remota.

### 2.1. Dirección de escucha

En lugar de modificar `postgresql.conf` (que puede sobrescribirse en futuras actualizaciones del paquete), añadimos un fichero propio en `conf.d/`.  En debian se incluye mediante `include_dir = 'conf.d'`.

```
sudo tee /etc/postgresql/17/main/conf.d/99-remoto.conf << 'EOF'
listen_addresses = 'TU_IP_SERVIDOR'
EOF
```

> Si prefieres que escuche en todas las interfaces, usa `listen_addresses = '*'`. Es más cómodo, pero expone el servicio en todas las redes del equipo; es preferible indicar la IP concreta.

### 2.2. Reglas de acceso (`pg_hba.conf`)

El fichero `pg_hba.conf` no admite `conf.d`, así que añadimos nuestra regla al final. Cada línea tiene el formato `tipo  base_de_datos  usuario  origen  método`.

> Para el ejemplo permitiré el acceso remoto de cualquier usuario a cualquier base siempre que sea desde la dirección de mi cliente, para hacerlo mas codo para el futuro, pero si quisiésemos podríamos ser mucho mas estrictos con entradas únicas para cada usuario o cada base.

```
sudo tee -a /etc/postgresql/17/main/pg_hba.conf << 'EOF'

# Acceso remoto a la base de datos prueba
host    all             all             TU_IP_CLIENTE/32        scram-sha-256
EOF
```

> Podemos permitir una red completa usando notación CIDR en lugar de `%` como en MariaDB, por ejemplo `192.168.1.0/24`. En el ejemplo lo limitamos a una única dirección IP con `/32`.

### 2.3. Reinicio y verificación

Un cambio en `listen_addresses` requiere reiniciar el servicio (un simple `reload` no basta). Los cambios solo en `pg_hba.conf` se aplican con `reload`.

```
sudo systemctl restart postgresql
```

Verificamos que el proceso escucha ahora en la IP indicada por el puerto 5432:

```
sudo ss -tlnp | grep 5432
```

```
debian@postgres:~$ sudo ss -tlnp | grep 5432
LISTEN 0      200    192.168.122.251:5432      0.0.0.0:*    users:(("postgres",pid=3832,fd=6))
```
---

## 3. Servidor: Creación de Base de Datos y Usuario Remoto

Para esta prueba llamaré a la base de datos `prueba` y al usuario `SCOTT`. Ademas le daré a el usuario todos los permisos sobre la base(esto ultimo no es necesario ya que al ser el owner de la bd ya puede conectarse y crear tablas y relaciones con normalidad, solo lo hago para la prueba pero no es buena practica).

```
sudo -u postgres psql << 'EOF'
CREATE ROLE scott LOGIN PASSWORD '<PASSWORD>';
CREATE DATABASE prueba OWNER scott;
GRANT ALL PRIVILEGES ON DATABASE prueba TO scott;
EOF
```

> Los identificadores sin comillas se convierten a minúsculas en PostgreSQL, así que `SCOTT` y `scott` son el mismo rol. Se recomienda usar siempre minúsculas.

Comprobamos que el rol, la base de datos y sus permisos quedaron correctamente definidos:

```
sudo -u postgres psql -c "\du scott"
sudo -u postgres psql -c "\l prueba"
```

```
debian@postgres:~$ sudo -u postgres psql -c "\du scott"
     List of roles
 Role name | Attributes
-----------+------------
 scott     |

debian@postgres:~$ sudo -u postgres psql -c "\l prueba"
                                            List of databases
  Name  | Owner | Encoding | Locale Provider | Collate |  Ctype  | Locale | ICU Rules | Access privileges
--------+-------+----------+-----------------+---------+---------+--------+-----------+-------------------
 prueba | scott | UTF8     | libc            | C.UTF-8 | C.UTF-8 |        |           | =Tc/scott        +
        |       |          |                 |         |         |        |           | scott=CTc/scott
(1 row)
```

---

## 4. Cliente: Instalación y Conexión

Los siguientes pasos se realizan en el equipo remoto desde el que se quiere acceder.

### Instalación del cliente

Solo necesitamos el cliente de línea de comandos (`psql`), no el servidor:

```
sudo apt update
sudo apt install -y postgresql-client
```

### Comprobación de alcance de red

Antes de autenticarnos, podemos comprobar si el puerto del servidor es alcanzable desde el cliente:

```
nc -zv TU_IP_SERVIDOR 5432
```

```
debian@cliente:~$ nc -zv 192.168.122.251 5432
Connection to 192.168.122.251 5432 port [tcp/postgresql] succeeded!
```

> Si `nc` no está disponible: `sudo apt install -y netcat-openbsd`.
>
> También existe `pg_isready -h TU_IP_SERVIDOR -p 5432`, incluida en `postgresql-client`, que comprueba si el servidor acepta conexiones.

### Fichero de servicios del cliente (opcional)

Equivale al alias de `tnsnames.ora` en Oracle: guardamos servidor, puerto, usuario y base de datos bajo un nombre de servicio en `~/.pg_service.conf` para no repetirlos en cada conexión. No guardamos la contraseña; se solicitará por teclado.

```
tee ~/.pg_service.conf << 'EOF'
[prueba]
host = TU_IP_SERVIDOR
port = 5432
user = scott
dbname = prueba
EOF

chmod 600 ~/.pg_service.conf
```

### Prueba de conectividad con la base de datos

Con el fichero anterior basta con:

```
psql service=prueba
```

Sin él, se indican los parámetros de forma explícita:

```
psql -h TU_IP_SERVIDOR -p 5432 -U scott -d prueba
```

> La opción `-p` (puerto) es opcional mientras que el puerto sea el 5432 (el de por defecto). La contraseña se solicita de forma interactiva; para no teclearla cada vez se puede usar el fichero `~/.pgpass` (con permisos `600`), aunque guarda la contraseña en texto plano.

```
psql -h 192.168.122.251 -U scott -d prueba
Contraseña para usuario scott:
psql (17.11 (Debian 17.11-0+deb13u1))
Conexión SSL (protocolo: TLSv1.3, cifrado: TLS_AES_256_GCM_SHA384, compresión: desactivado, ALPN: postgresql)
Digite «help» para obtener ayuda.

prueba=>
```

Una vez dentro, confirmamos la información de la conexión y, después, usuario, origen y versión de la sesión:

```
\conninfo
```

```
prueba=> \conninfo
Está conectado a la base de datos «prueba» como el usuario «scott» en el servidor «192.168.122.251» port «5432».
Conexión SSL (protocolo: TLSv1.3, cifrado: TLS_AES_256_GCM_SHA384, compresión: desactivado, ALPN: postgresql)
```