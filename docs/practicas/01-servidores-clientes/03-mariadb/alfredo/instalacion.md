# Instalación de MariaDB Server y MariaDB client en Debian 13 y Conexión de Clientes Remotos (Por Alfredo)

Esta guía describe el procedimiento para instalar MariaDB Server en Debian 13 (Trixie), configurarlo para aceptar conexiones desde otros equipos de la red y preparar un cliente remoto que se conecte a él.


---

## 1. Servidor: Instalación de MariaDB

Instalamos el servidor desde los repositorios oficiales de Debian:

```
sudo apt update
sudo apt install -y mariadb-server

```

Comprobamos la versión instalada, que el servicio está activo y habilitado en el arranque:

```
mariadb --version
sudo systemctl status mariadb --no-pager

```

```
debian@mariadb:~$ mariadb --version
mariadb from 11.8.6-MariaDB, client 15.2 for debian-linux-gnu (x86_64) using  EditLine wrapper

debian@mariadb:~$ sudo systemctl status mariadb --no-pager
● mariadb.service - MariaDB 11.8.6 database server
     Loaded: loaded (/usr/lib/systemd/system/mariadb.service; enabled; preset: enabled)
     Active: active (running) since Thu 2026-10-08 15:29:00 UTC; 26s ago
 Invocation: 1ceff05da9064d9993d9fdb4cc549056
       Docs: man:mariadbd(8)
             https://mariadb.com/kb/en/library/systemd/
    Process: 613 ExecStartPre=/bin/sh -c [ ! -e /usr/bin/galera_recovery ] && VAR= ||   VAR=`/usr/bin/galera_recovery`; [ $? -eq 0 ]   && echo _WSREP_START_POSITION=$VAR > /run/mysqld/wsrep-start-position || exit 1 (code=exited, status=0/SUCCESS)
    Process: 709 ExecStartPost=/bin/rm -f /run/mysqld/wsrep-start-position /run/mysqld/wsrep-new-cluster (code=exited, status=0/SUCCESS)
    Process: 711 ExecStartPost=/etc/mysql/debian-start (code=exited, status=0/SUCCESS)
   Main PID: 683 (mariadbd)
     Status: "Taking your SQL requests now..."
      Tasks: 14 (limit: 15297)
     Memory: 159.3M (peak: 164M)
        CPU: 1.190s
     CGroup: /system.slice/mariadb.service
             └─683 /usr/sbin/mariadbd

```

### Script *mariadb-secre-installation*

El script `mariadb-secure-installation` permite establecer la contraseña de `root`, eliminar usuarios anónimos, deshabilitar el acceso remoto de `root` y borrar la base de datos de pruebas. Es interactivo; en Debian la cuenta `root` de MariaDB se autentica por socket (`unix_socket`), por lo que se puede aceptar la opción de mantenerlo así.

```
sudo mariadb-secure-installation

```

---

## 2. Servidor: Configuración para Escuchar en Red

En lugar de modificar `50-server.cnf` (que puede sobrescribirse en futuras actualizaciones del paquete), añadimos un fichero propio. Los ficheros de `/etc/mysql/mariadb.conf.d/` se leen en orden alfabético, así que `99-remoto.cnf` prevalece sobre la configuración por defecto.

```
sudo tee /etc/mysql/mariadb.conf.d/99-remoto.cnf << 'EOF'
[mysqld]
bind-address = TU_IP_SERVIDOR
EOF

sudo systemctl restart mariadb

```

Verificamos que el proceso escucha ahora en todas las interfaces por el puerto 3306:

```
sudo ss -tlnp | grep 3306

```

```
debian@mariadb:~$ sudo ss -tlnp | grep 3306
LISTEN 0      80     192.168.122.138:3306      0.0.0.0:*    users:(("mariadbd",pid=1297,fd=28))

```

---

## 3. Servidor: Creación de Base de Datos y Usuario Remoto

En MariaDB una cuenta se identifica por **usuario@origen**. Creamos el usuario permitiendo únicamente conexiones desde la red de los clientes, y le damos privilegios solo sobre su base de datos. Podemos poner el origen del usuario como una red completa usando el comodin %, por ejemplo 192.168.1.%, en el ejemplo yo lo pondre unicamente a una direccion ip.
(para esta prueba llamare a bd prueba y al usuario SCOTT)

```
sudo mariadb << 'EOF'
CREATE DATABASE prueba;
CREATE USER 'SCOTT'@'TU_RED_CLIENTE' IDENTIFIED BY '<PASSWORD>';
GRANT ALL PRIVILEGES ON prueba.* TO 'SCOTT'@'TU_RED_CLIENTE';
FLUSH PRIVILEGES;
EOF

```

Comprobamos que el usuario y sus permisos quedaron correctamente definidos:

```
sudo mariadb -e "SELECT user, host FROM mysql.user WHERE user='SCOTT';"
sudo mariadb -e "SHOW GRANTS FOR 'SCOTT'@'TU_RED_CLIENTE';"

```

```
debian@mariadb:~$ sudo mariadb -e "SELECT user, host FROM mysql.user WHERE user='SCOTT';"
+-------+---------------+
| User  | Host          |
+-------+---------------+
| SCOTT | 192.168.122.1 |
+-------+---------------+
debian@mariadb:~$ sudo mariadb -e "SHOW GRANTS FOR 'SCOTT'@'192.168.122.1';"
+------------------------------------------------------------------------------------------------------------------+
| Grants for SCOTT@192.168.122.1                                                                                   |
+------------------------------------------------------------------------------------------------------------------+
| GRANT USAGE ON *.* TO `SCOTT`@`192.168.122.1` IDENTIFIED BY PASSWORD '*92AB35BF0769A580EAD68F4C9AC350C8FBAFE856' |
| GRANT ALL PRIVILEGES ON `prueba`.* TO `SCOTT`@`192.168.122.1`                                                    |
+------------------------------------------------------------------------------------------------------------------+
debian@mariadb:~$

```

---

## 4. Cliente: Instalación y Conexión

Los siguientes pasos se realizan en el equipo remoto desde el que se quiere acceder.

### Instalación del cliente

Solo necesitamos el cliente de línea de comandos, no el servidor:

```
sudo apt update
sudo apt install -y mariadb-client

```

### Comprobación de alcance de red

Antes de autenticarnos, podemos si el puerto del servidor es alcanzable desde el cliente:

```
nc -zv TU_IP_SERVIDOR 3306

```

```
debian@cliente:~$ nc -zv 192.168.122.138 3306
Connection to 192.168.122.138 3306 port [tcp/mysql] succeeded!

```

> Si `nc` no está disponible: `sudo apt install -y netcat-openbsd`.

### Fichero de configuración del cliente (opcional)

Equivale al alias de `tnsnames.ora` en Oracle: guardamos servidor, puerto, usuario y base de datos por defecto en `~/.my.cnf` para no repetirlos en cada conexión. No guardamos la contraseña; se solicitará por teclado.

```
tee ~/.my.cnf << 'EOF'
[client]
host = TU_IP_SERVIDOR
port = 3306
user = SCOTT
database = prueba
EOF

chmod 600 ~/.my.cnf

```

### Prueba de conectividad con la base de datos

Con el fichero anterior basta con:

```
mariadb -p

```

Sin él, se indican los parámetros de forma explícita:

```
mariadb -h TU_IP_SERVIDOR -P 3306 -u SCOTT -p prueba

```
> La opcion -P o puerto es opcional mientras que el puerto sea el 3306 (el por defecto)

```
debian@cliente:~$ mariadb -h 192.168.122.138 -u SCOTT -p prueba
Enter password:
Welcome to the MariaDB monitor.  Commands end with ; or \g.
Your MariaDB connection id is 44
Server version: 11.8.6-MariaDB-0+deb13u1 from Debian -- Please help get to 10k stars at https://github.com/MariaDB/Server

Copyright (c) 2000, 2018, Oracle, MariaDB Corporation Ab and others.

Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

MariaDB [prueba]>

```

Una vez dentro, confirmamos usuario, origen y versión de la sesión:

```
SELECT CURRENT_USER(), USER(), VERSION();

```

```
MariaDB [prueba]> SELECT CURRENT_USER(), USER(), VERSION();
+---------------------+----------------+--------------------------------------+
| CURRENT_USER()      | USER()         | VERSION()                            |
+---------------------+----------------+--------------------------------------+
| SCOTT@192.168.122.1 | SCOTT@_gateway | 11.8.6-MariaDB-0+deb13u1 from Debian |
+---------------------+----------------+--------------------------------------+
1 row in set (0,001 sec)

MariaDB [prueba]>

```
